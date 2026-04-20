# Spec / Note Handoff

When a note trigger invokes Steward:

- attach the source note path
- attach the selected text or paragraph
- attach the anchor or line range
- record whether the handoff came from a mention, ribbon, or command

Do not mutate the current note on trigger.

After the reply, the plugin may offer explicit write-back actions:

- insert as a callout
- replace the selection
- create a linked note

Keep the current note protected until the user chooses a write-back action.
