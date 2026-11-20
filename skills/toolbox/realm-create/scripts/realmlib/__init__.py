"""realm: wake subscribed herdr panes that have unread Agent Mail.

launchd runs `realm tick` every 15 s; each subscriber is woken at most once per its own interval,
only when its Agent Mail inbox has unread messages and herdr reports its agent neither working nor blocked.
A `prompt` subscriber is woken by typing WAKE_TEXT + Enter into its pane. An `aside` subscriber is never
typed into: it gets a `mail` pane token, a sidebar label that never pops up or sounds.
"""
