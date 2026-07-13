"""
Review Request System — Generates review request assets for Google, SMS, email, in-store.
"""


def generate_review_request_pack() -> dict:
    """Generate a complete review request system for Temporary Satisfaction."""

    return {
        "google_review": {
            "title": "Google Review Request",
            "short_ask": "We'd love your feedback! If you enjoyed your visit, a quick Google review helps other shoppers find us.",
            "qr_card_text": "Loved your visit?\nLeave us a Google review.\nScan below — takes 30 seconds.",
            "follow_up_text": "Thank you for visiting Temporary Satisfaction! If you have a moment, we'd really appreciate a Google review. It helps other Long Beach shoppers find a judgment-free place to explore. [LINK]",
            "prompt_suggestions": [
                "What made you feel comfortable shopping here?",
                "How would you describe the staff's approach?",
                "What surprised you about the experience?",
                "Would you recommend us to a friend? Why?",
            ],
        },
        "sms_templates": {
            "title": "SMS Review Requests",
            "post_purchase_same_day": "Hey! Thanks for visiting Temporary Satisfaction today. If you have 30 seconds, a Google review really helps us out: [LINK] — no pressure, just appreciated.",
            "post_purchase_next_day": "Hi from Temporary Satisfaction! Hope you're enjoying your purchase. If you had a good experience, we'd love a quick review: [LINK]. Thanks for supporting local!",
            "repeat_customer": "Hey [NAME]! Thanks for being a returning customer. If you haven't left a review yet, we'd love to hear what keeps you coming back: [LINK]",
        },
        "email_templates": {
            "title": "Email Review Requests",
            "post_purchase": {
                "subject": "How was your visit to Temporary Satisfaction?",
                "body": """Hi there,

Thank you for visiting Temporary Satisfaction! We hope you found exactly what you were looking for.

If you have a moment, we'd really appreciate a quick Google review. It helps other Long Beach shoppers discover a comfortable, judgment-free place to explore intimate wellness.

Leave a review here: [GOOGLE REVIEW LINK]

A few things you might mention (only if you feel like it):
- How the experience felt compared to what you expected
- Whether the staff was helpful without being pushy
- What you appreciated about the selection or environment

Thank you for supporting a local, women-founded business.

Warmly,
The Temporary Satisfaction Team""",
            },
            "loyalty_program": {
                "subject": "You've been amazing — would you share the love?",
                "body": """Hi [NAME],

You've visited us [X] times now, and we genuinely appreciate you choosing Temporary Satisfaction.

If you haven't already, a Google review would mean the world to us. It takes about 30 seconds and directly helps other shoppers in Long Beach find a space where they feel safe and supported.

Review us here: [GOOGLE REVIEW LINK]

Thank you for being part of what makes this community special.

With gratitude,
The TS Team""",
            },
        },
        "in_store_signage": {
            "title": "In-Store Signage & QR Display",
            "counter_sign": {
                "headline": "Enjoyed your visit?",
                "body": "A quick Google review helps others find us.\nScan below — it takes 30 seconds.",
                "footer": "Thank you for supporting local.",
            },
            "mirror_sign": {
                "headline": "Feeling good?",
                "body": "Tell us about it.\nScan for a quick Google review.",
                "footer": "Your words help others find a judgment-free space.",
            },
            "bag_insert": {
                "headline": "Thank you for choosing Temporary Satisfaction",
                "body": "If you loved your experience, a Google review helps us reach more shoppers who deserve a comfortable, curated space.\n\nScan the QR code or visit: [SHORT LINK]",
                "footer": "Long Beach's judgment-free intimate boutique.",
            },
        },
        "staff_scripts": {
            "title": "Staff Ask Scripts",
            "at_checkout_casual": "Hey, if you enjoyed shopping today, we'd really appreciate a Google review. There's a QR code right here if you have a second — totally no pressure.",
            "after_helpful_interaction": "I'm glad I could help! If you have a moment later, a quick Google review really helps other people find us. We have a QR card here, or I can text you the link.",
            "for_repeat_customers": "You always come back and we love that! Have you ever left us a Google review? It really helps new customers feel confident about visiting.",
            "do_not_say": [
                "Don't ask if they seem rushed or uncomfortable",
                "Don't ask immediately after a sensitive purchase",
                "Don't ask more than once per visit",
                "Don't offer discounts or incentives for reviews (Google policy violation)",
                "Don't tell them what to write",
            ],
        },
        "timing_workflow": {
            "title": "When to Ask",
            "rules": [
                {"timing": "At checkout", "when": "Customer seems happy, had a good interaction, is relaxed", "method": "Staff verbal + QR card"},
                {"timing": "Same day (2-4 hours after)", "when": "Post-purchase window while experience is fresh", "method": "SMS"},
                {"timing": "Next day", "when": "Follow-up for online orders or if same-day felt too soon", "method": "Email or SMS"},
                {"timing": "After 3rd visit", "when": "Repeat customer who clearly enjoys the store", "method": "Personal ask from staff or email"},
                {"timing": "Never", "when": "Customer seemed uncomfortable, was browsing only, or asked for privacy", "method": "None — respect the moment"},
            ],
            "frequency_rule": "Maximum 1 ask per customer per 30 days. If they said no or ignored, do not ask again for 90 days.",
        },
        "implementation_steps": [
            "1. Set up Google Business Profile review link (short URL)",
            "2. Generate QR code pointing to the review link",
            "3. Print counter sign + bag insert with QR code",
            "4. Add review request to post-purchase email flow",
            "5. Add SMS review request to post-purchase sequence (2-4 hour delay)",
            "6. Brief staff on scripts + timing + do-not-say list",
            "7. Track review count weekly — goal: 2-3 new reviews per week",
        ],
    }
