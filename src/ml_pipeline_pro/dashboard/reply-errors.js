// Fixed public explanations: never render arbitrary diagnostic metadata.
const reasons = new Map([
  ["provider_response:invalid_envelope", "The model returned an unsupported response format."],
  ["provider_response:invalid_json", "The model returned malformed JSON."],
  ["provider_response:invalid_usage", "The model reported invalid token usage."],
  ["reply_schema:invalid_json", "The model returned malformed reply JSON."],
  ["reply_schema:invalid_tool_call", "The model returned an invalid function call."],
  ["reply_schema:invalid_reply_schema", "The reply did not match the required format."],
  ["host_step:invalid_step", "The model returned an unsupported conversation step."],
  ["host_step:invalid_usage", "The model reported invalid token usage."],
  ["evidence_resolution:invalid_evidence", "The retrieved evidence could not be verified."],
  ["evidence_resolution:unknown_citation", "The reply cited a record that was not verified in this turn."],
  ["evidence_resolution:unsupported_fact_field", "The reply requested a fact field this agent does not support."],
  ["evidence_resolution:missing_fact_field", "The reply requested a fact missing from the retrieved record."],
  ["evidence_resolution:ambiguous_record", "The reply's fact reference did not identify one verified record."],
  ["evidence_resolution:nonscalar_fact", "The reply requested a grouped value instead of a single fact."],
]);

export function validationExplanation(error) {
  if (error?.code === "unsupported_model_algorithm") return "AI training and tuning support MLP only. Use the manual training form for logistic regression.";
  const details = error?.details;
  if (error?.code !== "model_invalid_response" ||
      typeof details?.validation_stage !== "string" ||
      typeof details?.validation_reason !== "string") return "";
  return reasons.get(`${details.validation_stage}:${details.validation_reason}`) || "";
}
