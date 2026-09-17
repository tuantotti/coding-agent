Add phone number validation to this signup flow.

Requirements:
- Add a `validate_phone_number` function that checks a phone number looks like
  a plausible E.164-ish number (starts with "+", 8-15 digits after that).
- Wire it into `handle_signup` so signup also requires a valid phone number,
  passed as a new `phone_number` argument.
- Follow the conventions already established in this codebase.
