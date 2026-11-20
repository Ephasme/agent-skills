"""realm: wake subscribed herdr panes when new Agent Mail lands for their agent.

launchd runs `realm tick` every 15 s. Each tick reads every subscriber's Agent Mail delivery events after its
stored cursor; the new message ids join the subscriber's `pending` set, and cursor and set are saved together,
so each delivery is handled once and survives restarts. A `prompt` subscriber with pending mail is woken by
typing WAKE_TEXT + Enter into its pane as soon as herdr reports its agent neither working nor blocked, and
only if some pending message is still unread. An `aside` subscriber is never typed into: it gets a `mail`
pane token, a sidebar label that never pops up or sounds.
"""
