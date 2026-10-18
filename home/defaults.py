"""Editorial starter sections for the SLQS homepage.

These are copy suggestions, NOT factual claims of membership counts, dates or events.
The management command installs them only when the editor has no custom blocks.
"""


def starter_home_sections():
    return [
        {"type": "values_strip", "value": {"items": [
            {"label": "Professional growth", "detail": "Learning and development"},
            {"label": "Meaningful networks", "detail": "People and connections"},
            {"label": "Shared expertise", "detail": "Knowledge across borders"},
            {"label": "Stronger together", "detail": "A supportive community"},
        ]}},
        {"type": "intro_story", "value": {
            "eyebrow": "WHO WE ARE", "title": "A stronger professional community, together.",
            "body": "<p>SLQS Saudi Arabia brings Sri Lankan quantity surveying professionals together to exchange knowledge, build connections and support professional growth throughout the Kingdom.</p><p>One community, many perspectives. Our approach is shaped by experience, collaboration and a shared commitment to professional excellence.</p>",
            "image_position": "right", "button_label": "Discover SLQS",
        }},
        {"type": "services_grid", "value": {
            "eyebrow": "WHAT WE DO", "title": "Creating more ways to connect and grow.",
            "description": "Four areas of focus, one professional community.",
            "cards": [
                {"kicker": "01 · DEVELOPMENT", "title": "Professional development", "description": "Conversations, learning opportunities and resources that support QS practice."},
                {"kicker": "02 · NETWORK", "title": "Professional networking", "description": "Build meaningful connections with QS professionals throughout Saudi Arabia."},
                {"kicker": "03 · INSIGHT", "title": "Knowledge exchange", "description": "Share practical experience and explore emerging industry perspectives."},
                {"kicker": "04 · COMMUNITY", "title": "Community engagement", "description": "Come together through SLQS activities, events and collective initiatives."},
            ],
        }},
        {"type": "events_feed", "value": {
            "eyebrow": "OUR EVENTS", "title": "Where conversations become connections.",
            "description": "Discover SLQS gatherings, learning sessions and upcoming activities as they are published.",
        }},
        {"type": "news_feed", "value": {
            "eyebrow": "NEWSROOM", "title": "Ideas, updates and what's next.",
            "description": "Official association updates, announcements and professional insights from our community.",
        }},
        {"type": "join_banner", "value": {
            "eyebrow": "JOIN THE COMMUNITY", "title": "Your professional network starts here.",
            "description": "Become part of a community of Sri Lankan quantity surveyors across Saudi Arabia.",
            "button_label": "Apply for membership",
        }},
    ]
