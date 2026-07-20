"""Pure data — no engine imports, mirrors app.conversations.constants' pattern.

Customer Feedback (Phase X Stage 7) currently has exactly one real source:
the webchat guest's thumbs-up/down at the end of a turn (app.webchat.schemas
.WebchatFeedbackIn, RATING_VALUES). This module's own FEEDBACK_RATINGS
deliberately mirrors that vocabulary rather than inventing a star-rating
scale no part of the product actually collects yet — see
app/feedback/service.py's record_webchat_feedback for the one write path.
"""

FEEDBACK_CATEGORIES = ("website_chat", "general")

FEEDBACK_RATINGS = ("up", "down")

FEEDBACK_STATUSES = ("new", "reviewed", "actioned", "dismissed")
