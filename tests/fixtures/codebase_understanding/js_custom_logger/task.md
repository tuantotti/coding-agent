Add a new route handler `updateUserProfile(request)` in
`src/routes/updateUserProfile.js` that:

- Reads `userId` from `request.params` and `name` from `request.body`.
- Requires both to be present.
- Returns `{ userId, name }` on success.

Follow the conventions already established in this codebase.
