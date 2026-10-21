"""The parts of the app that are not a feature: the secret store, the YouTube
client and the exporter.

These three modules used to live in the research package. The research
feature left the desktop app, but the Social Discovery feature depends on
all three, so they moved up here rather than being rebuilt.
"""
