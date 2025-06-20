prospect_schema = {
  "id": "number",
  "business_entity_id": "number",
  "first_name": "string",
  "last_name": "string",
  "full_name": "string",
  "avatar": "string",
  "source": "string",
  "email": "string",
  "phone": "string",
  "phone_type": "string",
  "status": "string",
  "address": "string",
  "city": "string",
  "unit_number": "string",
  "birthday": "string",
  "state": "string",
  "zip": "string",
  "assigned_to": "number",
  "assigned_user": {
    "id": "number",
    "name": "string",
    "email": "string",
    "phone": "string",
    "avatar_url": "string"
  },
  "do_not_call": "boolean",
  "last_contact": "datetime",
  "last_conversation": "datetime",
  "last_subject": "string",
  "timezone": "string",
  "shared_users": [
    {
      "id": "number",
      "name": "string",
      "email": "string",
      "phone": "string",
      "avatar_url": "string"
    }
  ],
  "stage_assigned_at": "string",
  "created_at": "object",
  "updated_at": "object",
  "business": {
    "id": "number",
    "external_id": "string",
    "name": "string"
  },
  "campaigns": [
    {
      "id": "number",
      "name": "string",
      "sequence_start": "string"
    }
  ],
  "tags": [
    {
      "id": "number",
      "name": "string",
      "sequence_start": "string"
    }
  ],
  "pipeline": {
    "id": "number",
    "name": "string"
  },
  "pipeline_stage": {
    "id": "number",
    "name": "string",
    "pipeline_id": "number"
  },
  "custom_status": {
    "id": "number",
    "name": "string",
    "sub_statuses": [
      {
        "id": "number",
        "name": "string",
        "created_at": "object",
        "updated_at": "object"
      }
    ],
    "business_tag": "number",
    "created_at": "object",
    "updated_at": "object"
  },
  "custom_sub_status": {
    "id": "number",
    "name": "string",
    "created_at": "object",
    "updated_at": "object"
  },
  "opt_outs": [
    "string"
  ],
  "mortgage": {
    "prospect_id": "number",
    "lead_id": "string",
    "company_name": "string",
    "birthday": "datetime",
    "zip": "string",
    "loan_amount": "string",
    "down_payment": "string",
    "loan_program": "string",
    "credit_score": "string",
    "loan_type": "string",
    "loan_purpose": "string",
    "property_value": "string",
    "property_address": "string",
    "property_unit_number": "string",
    "property_city": "string",
    "property_state": "string",
    "property_zip": "string",
    "property_county": "string",
    "found_home": "number",
    "bankruptcy": "number",
    "foreclosure": "number",
    "working_with_agent": "number",
    "agent_name": "string",
    "lead_source": "string",
    "interest_rate": "string",
    "requested_apr": "string",
    "property_type": "string",
    "property_use": "string",
    "bankruptcy_details": "string",
    "foreclosure_details": "string",
    "occupation": "string",
    "household_income": "string",
    "current_step": "string",
    "purchase_price": "string",
    "cash_out_amount": "string",
    "application_date": "datetime",
    "close_date": "string",
    "rate_is_locked": "number",
    "other_income": "string",
    "lien_position": "number",
    "amortization_type": "number",
    "amortization_term": "number",
    "monthly_payment": "string",
    "new_loan_amount": "string",
    "lender": "string",
    "agent_phone": "string",
    "agent_email": "string",
    "agent_address": "string",
    "seller_agent_name": "string",
    "seller_agent_phone": "string",
    "seller_agent_email": "string",
    "seller_agent_address": "string",
    "rate_lock_date": "string",
    "monthly_income": "string",
    "org_id": "number"
  },
  "recruiting": {
    "prospect_id": "number",
    "job_title": "string",
    "company_name": "string",
    "linkedin_url": "string",
    "start_date": "datetime",
    "nmls": "string",
    "consumer_facing": "string",
    "types_of_loan": "string",
    "volume_monetary": "string",
    "volume_amount": "string",
    "software_utilized": "string",
    "lead_sources": "string",
    "state_licenses": "string",
    "work_from_home": "number",
    "compensation_range": "string",
    "org_id": "number"
  },
  "insurance": {
    "prospect_id": "number",
    "referral_source": "string",
    "company_name": "string",
    "zip": "string",
    "insurance_city": "string",
    "insurance_state": "string",
    "insurance_address": "string",
    "birthday": "string",
    "apartment_number": "string",
    "marital_status": "string",
    "height": "string",
    "weight": "string",
    "weight_change": "string",
    "income": "string",
    "occupation": "string",
    "work_phone": "string",
    "net_worth": "string",
    "insurance_declined": "number",
    "gender": "number",
    "dependents": "number",
    "smoker": "number",
    "created_at": "string",
    "updated_at": "string",
    "credit_standing": "string",
    "flood_interest": "number",
    "earthquake_interest": "number",
    "deductible": "string",
    "coverage_amount": "string",
    "liability_amount": "string",
    "dui": "number",
    "occupancy_status": "string",
    "property_use": "string",
    "property_type": "string",
    "license_status": "string",
    "org_id": "number"
  },
  "custom": [
    {
      "id": "number",
      "prospect_id": "number",
      "custom_field_id": "number",
      "body": "string"
    }
  ],
  "contact_information": [
    {
      "id": "number",
      "prospect_id": "number",
      "type": "string",
      "content": "string",
      "phone_type": "string",
      "created_at": "object",
      "updated_at": "object"
    }
  ],
  "external_id": "string",
  "tasks_due_today_count": "string",
  "tasks_overdue_count": "string"
}
