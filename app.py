from quart_cors import cors
from functools import wraps
from pydantic import BaseModel, Field
import os, json, logging, aiohttp
from quart import Quart, request, jsonify
from openai import OpenAIError, RateLimitError, AsyncOpenAI
from modal import Image, App, Secret, asgi_app
from repository.context import MessageContextBonzo
from prompts import prompts

quart_app = Quart(__name__)
quart_app = cors(
    quart_app,
    allow_origin="*",
    allow_headers="*",
    allow_methods=["POST", "DELETE"]
)

# Create a Modal App and Network File System
modal_app = App("rad-integration")
aclient = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

image = (
    Image.debian_slim()
    .pip_install_from_requirements("requirements.txt")
    .add_local_dir("repository", "/root/repository")
    .add_local_file("prompts.py", "/root/prompts.py")
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

context_store = MessageContextBonzo()

def get_api_key():
    return os.environ.get("API_KEY")

def require_api_key(f):
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        if request.headers.get('X-API-Key') and request.headers.get('X-API-Key') == get_api_key():
            return await f(*args, **kwargs)
        else:
            return jsonify({"error": "Unauthorized"}), 401

    return decorated_function

@quart_app.route("/upload_context", methods=["POST"])
@require_api_key
async def upload_context():
    try:
        data = await request.json
        id = data.get("id")
        context = data.get("context")
        goal = data.get("goal", None)
        tone = data.get("tone", None)
        schema_context = data.get("schema_context", [])

        if not id or not context or not isinstance(context, list):
            return jsonify({"error": "Missing required fields: id and context are required."}), 400

        if schema_context and not isinstance(schema_context, list):
            return jsonify({"error": "Invalid schema_context format. It must be a list of schemas."}), 400

        await context_store.update_message_context(id, context, goal, tone, schema_context)

        logging.info(f"Context uploaded successfully for id {id}.")
        return jsonify({
            "message": "Context uploaded successfully.",
            "id": id,
            "context": context,
            "goal": goal,
            "tone": tone,
            "schema_context": schema_context
        }), 200

    except Exception as e:
        logging.error(f"Error uploading context: {e}")
        return jsonify({"error": f"Error uploading context: {str(e)}"}), 500


class SchemaDiff(BaseModel):
    updated_schema: dict = Field(..., description="The updated version of the input schema")
    changes: dict = Field(..., description="The differences found from comparing user input")

    model_config = {
        "json_schema_extra": {
            "required": ["changes"]
        }
    }

class Sentiment(BaseModel):
    response: str
    conversation_status: str

@quart_app.route("/get_context/<id>", methods=["GET"])
@require_api_key
async def get_context(id):
    try:
        if not id:
            return jsonify({"error": "Missing required field: id"}), 400

        # Retrieve context from DynamoDB
        context = context_store.get(id)

        if not context:
            return jsonify({"error": "No context found for the given id"}), 404

        logging.info(f"Context retrieved successfully for id {id}.")
        return jsonify({"id": id, "context": context}), 200

    except Exception as e:
        logging.error(f"Error retrieving context: {e}")
        return jsonify({"error": f"Error retrieving context: {str(e)}"}), 500

@quart_app.route("/delete_context/<id>", methods=["DELETE"])
@require_api_key
async def delete_context(id):
    try:
        if not id:
            return jsonify({"error": "Missing required field: id"}), 400

        # Delete context from DynamoDB
        context_store.delete(id)

        logging.info(f"Context deleted successfully for id {id}.")
        return jsonify({"message": "Context deleted successfully.", "id": id}), 200

    except Exception as e:
        logging.error(f"Error deleting context: {e}")
        return jsonify({"error": f"Error deleting context: {str(e)}"}), 500

async def gpt_schema_update(aclient, schema_type: str, original: dict, user_message: str) -> tuple[dict, dict]:
    prompt = [
        {
            "role": "system",
            "content": (
                f"You are a data assistant. The following is the original {schema_type} schema. "
                "The user has provided a message that may contain updates to some fields in the schema.\n\n"
                "Your task is to extract ONLY the fields clearly mentioned in the message and return them as a nested object.\n"
                "- If a field is mentioned, include it in the result with its new value.\n"
                "- If a field is not mentioned, do not include it.\n"
                # "- If a field is nested (inside another object), return it as a nested object (e.g. { \"solar\": { \"firstName\": \"John\" } }).\n"
                "- If the same field name appears in multiple places in the schema, nest it correctly inside its parent object. Do not use dot notation. For example: { \"solar\": { \"firstName\": \"John\" } }.\n"
                "- If the user message provides general personal information (e.g. name, phone, email) without specifying context, map it to the most general applicant-level fields first (e.g. \"loanApplicant.firstName\" if applicable).\n"
                "- Do not make assumptions. If the user message is ambiguous, only extract fields when there is a clear match. Otherwise leave them out.\n\n"
                "Return ONLY the following JSON structure:\n"
                '{ \"extracted_fields\": { \"field_name\": value, ... } }\n\n'
                "Do not include the entire updated schema. Only include the fields mentioned in the user message.\n"
                "Respond ONLY with a JSON object. Do not include ```json or any explanation."
            )
        },
        {
            "role": "user",
            "content": json.dumps({
                "original_schema": original,
                "user_message": user_message
            })
        }
    ]

    response = await aclient.chat.completions.create(
        model="gpt-4o",
        messages=prompt,
        max_tokens=16384
    )

    raw = response.choices[0].message.content.strip()

    # Remove markdown code fences like ```json ... ```
    if raw.startswith("```json"):
        raw = raw.removeprefix("```json").strip()
    if raw.endswith("```"):
        raw = raw.removesuffix("```").strip()

    try:
        parsed = json.loads(raw)
        logger.info(f"Parsed schema update: {parsed}")

        # Extract token usage
        token_usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens
        }

        # Return extracted_fields only, token_usage
        return parsed.get("extracted_fields", {}), token_usage

    except json.JSONDecodeError:
        logger.error("GPT response was not valid JSON:\n" + raw)

        # Return empty dict with token usage if available
        token_usage = {
            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
            "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            "total_tokens": response.usage.total_tokens if response.usage else 0
        }

        return {}, token_usage

async def gpt_response(message_history, user_message, contexts=None, goal=None, tone_instructions=None, scope="all"):
    try:

        if scope == "all":
            prospect_schema_changes, prospect_schema_token_usage = await gpt_schema_update(aclient, "prospect", {}, user_message)
        elif scope == "prospect_info":
            prospect_schema_changes, prospect_schema_token_usage = await gpt_schema_update(aclient, "prospect", {}, user_message)

        change_log = ""

        if contexts and isinstance(contexts, list):
            context_str = "\n\n".join(contexts)
            context_note = (
                f"\n\nNote: The following relevant information has been supplied as context. "
                "Use this to better understand the conversation.\n"
                f"{context_str}"
            )
        else:
            context_note = (
                "\n\nNote: No additional context was supplied. "
                "If the question is unrelated to the topic, politely guide the conversation back on track."
            )

        # Construct final context message
        context_message = "".join([f"{msg['role']}: {msg['message']}\n" for msg in message_history])
        context_message += context_note

        if change_log:
            context_message += f"\n\nThe following updates were inferred from the conversation:\n{change_log}"

        response = await aclient.beta.chat.completions.parse(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"{tone_instructions or 'Provide clear, professional, and helpful responses in a conversational tone. Ensure accuracy while keeping interactions natural and engaging.'}\n\n"

                        f"The goal of this conversation is: {goal}\n\n"

                        "**Guidelines for Handling Conversations:**\n"
                        "- **conversation_over** → Use this only if the user clearly states they have no further questions.\n"
                        "- **human_intervention** → Escalate only if the user asks about scheduling, availability, or if no clear answer is found in the provided context.\n"
                        "- **continue_conversation** → If the topic allows for further discussion, offer additional insights or ask if the user would like more details.\n"
                        "- **out_of_scope** → If the user's question is unrelated, acknowledge it politely and redirect the conversation back to relevant topics.\n\n"

                        "**Handling Out-of-Scope Questions:**\n"
                        "If a user asks something unrelated, respond in a way that maintains a natural flow:\n"
                        "👤 User: 'What's the best Italian restaurant nearby?'\n"
                        "💬 Response: 'That sounds like a great topic! While I don't have restaurant recommendations, I'd be happy to assist with [specific topic]. Let me know how I can help!'\n\n"

                        "If the user continues with off-topic questions, acknowledge their curiosity but steer the conversation back in a professional and engaging manner."
                        "DO NOT USE EMOTICONS OR EMOJIS IN YOUR RESPONSES EVER.\n\n"
                    )
                },
                {"role": "user", "content": context_message}
            ],
            response_format=Sentiment,
            max_tokens=16384
        )

        parsed_sentiment = response.choices[0].message.parsed
        token_usage = response.usage.to_dict()

        # If GPT determines the question is off-topic, classify as 'out_of_scope'
        if "I'm not sure" in parsed_sentiment.response or "I can't help with that" in parsed_sentiment.response:
            parsed_sentiment.conversation_status = "out_of_scope"

        total_response_tokens = token_usage.get("total_tokens", 0)
        total_prospect_schema_tokens = prospect_schema_token_usage.get("total_tokens", 0)

        return {
            "response": parsed_sentiment.response,
            "conversation_status": parsed_sentiment.conversation_status,  # Tracks 'conversation_over', 'human_intervention', 'continue_conversation', 'out_of_scope'
            "changes": {
                "prospect_schema_data": prospect_schema_changes,
            },
            # "token_usage": {
            #     "response_tokens": total_response_tokens,
            #     "prospect_schema_tokens": total_prospect_schema_tokens,
            # }
        }

    except RateLimitError as e:
        logger.warning(f"Rate limit exceeded: {e}")
        return {"error": "Rate limit exceeded", "message": str(e)}, 429
    except OpenAIError as e:
        logger.error(f"OpenAI API error: {e}")
        return {"error": "OpenAI API error", "message": str(e)}, 500
    except json.JSONDecodeError:
        logger.error("Error decoding OpenAI response as JSON")
        return {"error": "Invalid response format from OpenAI"}, 500
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return {"error": "Unexpected error", "message": str(e)}, 400

@quart_app.route('/message-teli-data', methods=['POST'])
@require_api_key
async def message_teli_data():
    try:
        data = await request.json

        id = data.get("id")
        message_history = data.get("message_history")
        # context = data.get("context", [])
        tone = data.get("tone", None)
        goal = data.get("goal", None)
        scope = data.get("scope", "all")

        if not all([id, message_history]):
            return jsonify({"error": "Missing required fields"}), 400

        newest_message = message_history[-1]["message"]
        context = context_store.get(id)

        if not context:
            logger.info(f"No context found for id {id}. Using GPT alone.")
            return jsonify({"error": "No context found for the given id"}), 404

        logger.info("Using supplied context for GPT response.")
        gpt_response_data = await gpt_response(message_history, newest_message, context, goal=goal, tone_instructions=tone, scope=scope)

        # Handle response
        conversation_status = gpt_response_data["conversation_status"]
        response = gpt_response_data

        if conversation_status == 'human_intervention':
            logger.info("Human intervention required")
            return jsonify({"response": "Human intervention required"}), 200
        elif conversation_status == 'conversation_over':
            logger.info("Conversation complete")
            return jsonify({"response": "Conversation complete"}), 200
        elif conversation_status in ('continue_conversation', 'out_of_scope'):
            logger.info("Continue conversation")
            return jsonify({"response": response}), 200

    except Exception as e:
        logger.error(f"Error generating response: {e}")
        return jsonify({"error": str(e)}), 400

class Response(BaseModel):
    response: str

async def gpt_response_2(message_history, prospect_data, notes_content, prompt_id) -> dict:
    try:
        messages = [
            {
                "role": "system",
                "content": prompts[prompt_id]
            }
        ]

        # Add prospect data as context if available
        if prospect_data:
            messages.append({
                "role": "system",
                "content": f"Prospect Data: {json.dumps(prospect_data)}"
            })

        # Add prospect notes if available
        if notes_content:
            messages.append({
                "role": "system",
                "content": f"Prospect Notes: {json.dumps(notes_content)}"
            })

        # Add message history (filter out messages with empty content)
        valid_messages = [msg for msg in message_history if msg.get("content") and msg.get("content").strip()]
        messages.extend(valid_messages)

        response = await aclient.beta.chat.completions.parse(
            model="gpt-4.1-mini",
            messages=messages,
            response_format=Response,
            max_tokens=16384
        )

        parsed_response = response.choices[0].message.parsed
        token_usage = response.usage.to_dict()

        total_response_tokens = token_usage.get("total_tokens", 0)

        return {
            "response": parsed_response.response,
            "token_usage": {
                "total_tokens": total_response_tokens
            }
        }

    except Exception as e:
        logger.error(f"Error generating response: {e}")
        return {"error": str(e)}

@quart_app.route('/send_ai_message', methods=['POST'])
@require_api_key
async def send_ai_message():
    try:
        data = await request.json
        prospect_id = data.get("prospect_id")
        prompt_id = data.get("prompt_id")
        on_behalf_of = data.get("on_behalf_of")
        auth_token = data.get("auth_token")

        if not all([prospect_id, prompt_id, on_behalf_of, auth_token]):
            return jsonify({"error": "Missing required fields: prospect_id, prompt_id, on_behalf_of, and auth_token"}), 400

        url = f'https://app.getbonzo.com/api/v3/prospects/{prospect_id}/sms'
        comm_history = f'https://app.getbonzo.com/api/v3/prospects/{prospect_id}/communication'
        prospect_info = f'https://app.getbonzo.com/api/v3/prospects/{prospect_id}'
        prospect_notes = f'https://app.getbonzo.com/api/v3/prospects/{prospect_id}/notes'

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth_token}",
            "On-Behalf-Of": on_behalf_of
        }

        message_history = []

        async with aiohttp.ClientSession() as session:
            try:
                # Get communication history
                async with session.get(comm_history, headers=headers) as response:
                    if response.status != 200:
                        logger.error(f"Failed to fetch communication history: {response.status}")
                        return jsonify({"error": f"Failed to fetch communication history: {response.status}"}), 500

                    response_data = await response.json()
                    data = response_data.get("data")

                    if not data:
                        logger.warning(f"No communication history found for prospect {prospect_id}")
                        return jsonify({"error": "No communication history found"}), 404

                    # Build message history
                    for item in data:
                        if item.get("content"):  # Only add messages with content
                            message_history.append({
                                "role": "user" if item.get("direction") == "incoming" else "assistant",
                                "content": item.get("content")
                            })

                if not message_history:
                    logger.warning(f"No valid messages found in communication history for prospect {prospect_id}")
                    return jsonify({"error": "No valid messages found in communication history"}), 404

                # Get prospect data
                async with session.get(prospect_info, headers=headers) as response:
                    if response.status != 200:
                        logger.error(f"Failed to fetch prospect info: {response.status}")
                        return jsonify({"error": f"Failed to fetch prospect info: {response.status}"}), 500

                    res = await response.json()
                    prospect_data = res.get("data")

                if not prospect_data:
                    logger.warning(f"No prospect info found for prospect {prospect_id}")
                    return jsonify({"error": "No prospect info found"}), 404

                # Get prospect notes
                notes_content = []
                async with session.get(prospect_notes, headers=headers) as response:
                    if response.status == 200:
                        notes_response = await response.json()
                        notes_data = notes_response.get("data", [])
                        # Extract just the content from each note
                        notes_content = [note.get("content", "") for note in notes_data if note.get("content")]
                    else:
                        logger.warning(f"Failed to fetch prospect notes: {response.status}")

                # Generate GPT response
                gpt_response_data = await gpt_response_2(message_history, prospect_data, notes_content, prompt_id)

                if "error" in gpt_response_data:
                    logger.error(f"GPT response generation failed: {gpt_response_data['error']}")
                    return jsonify({"error": "Failed to generate AI response"}), 500

                # Send message
                payload = {
                    "message": gpt_response_data["response"],
                    "send_as": "owner"
                }

                async with session.post(url, headers=headers, json=payload) as send_response:
                    if send_response.status != 200:
                        logger.error(f"Failed to send message: {await send_response.json()}")
                        logger.error(f"Failed to send message: {send_response.status}")
                        return jsonify({"error": f"Failed to send message: {send_response.status}"}), 500

                    await send_response.json()
                    return jsonify({
                        "success": True,
                        "message_sent": gpt_response_data["response"],
                        # "token_usage": gpt_response_data["token_usage"]
                    }), 200

            except aiohttp.ClientError as e:
                logger.error(f"HTTP client error: {e}")
                return jsonify({"error": "Network error occurred"}), 500
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                return jsonify({"error": "Invalid response format from API"}), 500

    except Exception as e:
        logger.error(f"Unexpected error in send_ai_message: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

# For deployment with Modal
@modal_app.function(
    image=image,
    secrets=[Secret.from_name("rad-integration-secrets")]
)
@asgi_app()
def quart_asgi_app():
    return quart_app

# Local entrypoint for running the app
@modal_app.local_entrypoint()
def serve():
    quart_app.run()
