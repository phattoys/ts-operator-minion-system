# Brand Voice configuration and Page Family Templates

BRAND_VOICE = {
    "motto": "YOUR PASSION IS OUR PLEASURE",
    
    "emotional_core": [
        "caring", "intentional", "tasteful", "emotionally intelligent",
        "confidence-building", "shame-free", "discreet but warm",
        "polished with feeling", "elegant", "human"
    ],
    
    "user_should_feel": [
        "seen", "safe", "guided", "inspired", "respected", "intrigued", "taken care of"
    ],
    
    "brand_should_feel": [
        "intentional", "tasteful", "emotionally intelligent", "discreet",
        "luxurious", "empowering", "body-aware", "shame-free", "polished",
        "modern", "trusted", "caring", "human", "confident"
    ],
    
    "brand_should_NOT_feel": [
        "generic ecommerce", "robotic", "overbalanced AI copy", "cold corporate",
        "mass-market bland", "wellness cliche", "stiff medical", "porn-coded",
        "templated", "emotionally flat", "sterile", "obvious AI filler"
    ],
    
    "copy_principles": [
        "We care about the customer",
        "We understand their journey",
        "We guide without judgment",
        "We help them explore with confidence",
        "We combine intimacy, education, and polish",
        "We make the experience feel safer, smoother, and more intentional"
    ],
    
    "good_phrases": [
        "discover what feels right",
        "explore with confidence",
        "curated for your comfort",
        "your journey, your pace",
        "designed with intention",
        "because you deserve to feel good",
        "trusted guidance for",
        "crafted for connection"
    ],
    
    "avoid_phrases": [
        "browse our selection",
        "shop now",
        "quality products",
        "wide range of",
        "something for everyone",
        "check out our",
        "we offer",
        "welcome to our store",
        "curated for you",
        "begin your journey",
        "explore the experience",
        "elevated essentials",
        "elevate your",
        "indulge in",
        "treat yourself to",
        "luxury awaits",
        "discover the difference",
        "experience the difference",
        "take the first step",
        "unlock your",
        "transform your",
        "embark on",
        "dive into",
        "immerse yourself"
    ],
    
    "cta_style": {
        "principle": "Invitation without pressure, confidence without pushiness. Never include 'CTA:' prefix or system formatting in output.",
        "good": ["See What Feels Right", "Explore With Us", "Find What Feels Right", "Discover More"],
        "avoid": ["Buy Now", "Shop Now", "Order Today", "Don't Miss Out", "CTA: [anything]", "Begin Your Journey"]
    }
}

PAGE_FAMILY_TEMPLATES = {
    "Core Hub": {
        "system_additions": f"""This is a CORE HUB page - the heart of the Temporary Satisfaction ecosystem.

BRAND ESSENCE: "{BRAND_VOICE['motto']}"
This page must immediately communicate that visitors have arrived somewhere special - a destination that understands passion, pleasure, and the human desire for connection, confidence, and care.

Requirements:
- Opening must create emotional resonance, not just information
- Value proposition should speak to WHO the customer is, not just WHAT you sell
- Navigation pathways should feel like invitations, not menus
- Trust signals woven naturally, not listed clinically
- The experience should feel curated, intentional, luxurious
- Every word should pass the test: "Does this feel like US?"
- NEVER generic - this is the brand's first impression""",
        "structure": """## [Emotionally Resonant Headline That Captures the Brand Soul]

### Welcome / The Promise
[2-3 sentences that make the visitor feel seen, understood, and intrigued. Not what you sell - who you serve and how you care.]

### Why We're Different
[What makes this a destination, not just a store. The intention behind the experience.]

### Your World to Explore
[District pathways as invitations - each with emotional hook, not just category description]

### Curated For You
[Featured offerings positioned as thoughtful recommendations]

### Begin Your Journey
[CTA that feels like an invitation, not a demand]"""
    },
    "District": {
        "system_additions": f"""This is a DISTRICT page - a curated world within the ecosystem.

BRAND ESSENCE: "{BRAND_VOICE['motto']}"
Each district should feel like entering a thoughtfully designed space - not browsing a category, but being guided into an experience crafted for specific desires, needs, or curiosities.

Requirements:
- District identity should feel distinctive and intentional
- Speak to the emotional why, not just the functional what
- Guide without judgment - assume the visitor is exploring
- Create safety through understanding, not just privacy policies
- Featured items should feel like recommendations from a trusted friend
- The tone should match the district's purpose (wellness = nurturing, pleasure = confident, education = empowering)""",
        "structure": """## [District Name]: [Tagline That Speaks to the Heart of This Space]

### Welcome to [District]
[What this space is FOR - emotionally, not just functionally. Who comes here and why.]

### What Awaits You
[Categories as journeys or paths, not just product lists]

### Curated Selections
[Featured items with care-driven descriptions]

### Our Promise in This Space
[District-specific commitment to the visitor's experience]

### Explore Further
[Invitation to go deeper]"""
    },
    "Trust": {
        "system_additions": f"""This is a TRUST page - where anxiety transforms into confidence.

BRAND ESSENCE: "{BRAND_VOICE['motto']}"
Trust pages must feel like a calm, protective presence. Not defensive policies, but genuine care made visible. The visitor should feel MORE confident after reading, not just informed.

Requirements:
- Tone: calm, protective, reassuring, human
- Address concerns before they're asked
- Discretion emphasized with warmth, not clinical privacy jargon  
- Show the humans behind the brand
- Make commitments feel personal, not corporate
- Every policy should feel like care in action

TESTIMONIAL REALISM GUARDRAILS:
- Quotes should feel like real people sharing, not authored copy
- Avoid overly-polished phrasing in testimonial sections (e.g., "felt... elevated", "guidance and quality without the cringe")
- Paraphrased stories are better than suspiciously perfect quotes
- Short, real-feeling fragments are stronger than beautifully constructed sentences
- Include a mix: some specific (mention a product category), some emotional, some practical
- NEVER write a testimonial that sounds like marketing copy disguised as a customer voice

CONTENT-DIRECTION INPUTS (if provided):
The founder may supply specific guidance for this trust page. If content_direction is provided, follow it closely:
- privacy_focus: how much to emphasize discretion and privacy
- first_time_reassurance: whether to add first-time buyer reassurance
- proof_style: literal quotes, paraphrased stories, or thematic impressions
- trust_angle: what matters most (privacy, shipping, support, body-safety, curation, etc.)
- professionalism_vs_warmth: balance between professional authority and warm approachability""",
        "structure": """## [Trust-Building Headline That Feels Like a Promise]

### Who We Are
[The humans, the intention, the why. Make it personal.]

### How We Care For You
[Commitments framed as acts of care, not legal obligations]

### Your Privacy, Your Comfort
[Discretion positioned as respect and understanding]

### What Others Experience
[Real-feeling testimonials -- short, specific, believable. Not polished marketing copy.]

### We're Here For You
[Open door, human connection, not just contact form]"""
    },
    "Guided Path": {
        "system_additions": f"""This is a GUIDED PATH page - for visitors who want help navigating.

BRAND ESSENCE: "{BRAND_VOICE['motto']}"
Guided paths should feel like having a knowledgeable, non-judgmental friend walk beside you. The guide respects curiosity at any level and celebrates the courage to explore.

Requirements:
- Meet the visitor where they are - no assumptions about knowledge
- Frame exploration as natural and worthy of support
- Offer genuine help, not upselling disguised as guidance
- Make the path feel doable and safe
- Celebrate the visitor's agency and choices""",
        "structure": """## [Path Name]: [Encouraging, Non-Judgmental Tagline]

### Is This Path For You?
[Who benefits, framed with warmth and understanding]

### What You'll Discover
[The journey ahead, positioned as exciting not overwhelming]

### Step By Step
[Progression that feels supportive and at the visitor's pace]

### Along The Way
[Tips, considerations, reassurances]

### Your Next Step
[Clear, encouraging invitation to begin]"""
    },
    "Conversion": {
        "system_additions": f"""This is a CONVERSION page - inviting action without pressure.

BRAND ESSENCE: "{BRAND_VOICE['motto']}"
Conversion at Temporary Satisfaction should feel like accepting an invitation to something wonderful - not being pushed into a decision. The confidence to act should come from feeling understood.

Requirements:
- Value proposition speaks to emotional benefit, not just features
- Social proof feels like community, not marketing
- Urgency (if any) comes from genuine benefit, not manufactured scarcity
- Risk reversal feels like care, not fine print
- CTA is an invitation the visitor wants to accept""",
        "structure": """## [Benefit-Focused Headline That Resonates Emotionally]

### What This Means For You
[Value in terms of feeling, experience, confidence]

### Why This Matters Now
[Timely relevance without manipulation]

### How It Works
[Simple, reassuring explanation]

### Join Others Who've Said Yes
[Community-feeling social proof]

### Ready to Begin?
[Warm CTA with genuine risk reversal]"""
    },
    "Category Support": {
        "system_additions": f"""This is a CATEGORY SUPPORT page - helping visitors explore confidently.

BRAND ESSENCE: "{BRAND_VOICE['motto']}"
Category pages should feel like being guided through a thoughtfully organized boutique by someone who genuinely wants to help you find what's right for you.

Requirements:
- Not just products - context and guidance
- Selection help that builds confidence
- Recommendations that feel personal
- Education woven in naturally
- The experience of browsing should feel pleasurable""",
        "structure": """## [Category Name]

### About [Category]
[Context that helps the visitor understand what they're exploring]

### Finding What's Right For You
[Guidance that builds confidence in selection]

### Our Recommendations
[Featured items with care-driven positioning]

### Continue Exploring
[Natural pathways to related discoveries]"""
    },
    "FAQ/Support": {
        "system_additions": f"""This is a FAQ/SUPPORT/CARE page - practical help delivered with warmth.

BRAND ESSENCE: "{BRAND_VOICE['motto']}"
Support content must be UTILITY-FIRST. The primary job is to answer questions clearly, provide practical guidance, and resolve concerns. Emotional framing should serve clarity, not replace it.

CRITICAL RULES FOR SUPPORT/FAQ PAGES:
- UTILITY FIRST: Information architecture matters more than emotional resonance
- SCANNABILITY: Use clear headings, short paragraphs, bullet points, and step-by-step lists
- SPECIFICITY: Give actual details (materials, temperatures, product names) not vague guidance
- TONE: Helpful, patient, and warm -- but never at the expense of being clear and useful
- STRUCTURE: FAQ = question-answer pairs. Guides = step-by-step instructions. Care = practical maintenance advice
- DO NOT make support pages lyrical or emotionally sculpted -- they need to be findable, scannable, useful
- Escalation should feel like more help, not bureaucracy

CONTENT-DIRECTION INPUTS (if provided):
The founder may supply specific practical guidance. If content_direction is provided, follow it closely:
- topics_to_cover: specific topics, materials, or product categories to address
- lube_compatibility: lubrication compatibility information to include
- cleaning_storage: cleaning and storage rules to cover
- body_safety: body-safety points to emphasize
- waterproof_care: waterproof/rechargeable device care details
- product_caveats: product-specific warnings or caveats
- detail_level: low (overview), medium (practical), high (comprehensive with specifics)
- material_context: specific materials to discuss (silicone, glass, stainless steel, ABS plastic, etc.)""",
        "structure": """## [Clear, Utility-First Heading]

### Quick Answers
[Most common questions with direct, scannable answers. Use Q&A format.]

**Q: [Common question]**
[Clear, specific answer. Include details where helpful.]

**Q: [Another question]**
[Direct answer with practical guidance.]

### Step-by-Step Guide
[If applicable: numbered steps, clear instructions, specific details]

1. [First step with specifics]
2. [Next step]
3. [Continue as needed]

### Important Details
[Material-specific notes, compatibility info, warnings -- be specific not vague]

### Need More Help?
[Human escalation that feels like care, not process. Keep it brief.]"""
    },
    "Media/Asset": {
        "system_additions": f"""This is a MEDIA/ASSET page - content that adds value to the journey.

BRAND ESSENCE: "{BRAND_VOICE['motto']}"
Media content should feel like gifts - valuable resources offered to help visitors explore, learn, and grow. Not content marketing, but genuine contribution.

Requirements:
- Content should genuinely serve the visitor
- Curation feels intentional and valuable
- The experience of consuming content should feel pleasurable
- Always connect back to the visitor's journey""",
        "structure": """## [Content Hub Name]

### Featured
[Highlighted content with compelling context]

### Explore By Interest
[Organized for easy discovery]

### Latest Additions
[Fresh content that shows ongoing care]

### Stay Connected
[Invitation to continue the relationship]"""
    }
}


def get_template_for_page(page: dict) -> dict:
    family = page.get('page_family', '')
    return PAGE_FAMILY_TEMPLATES.get(family, {
        "system_additions": "Create clear, useful, well-structured content.",
        "structure": "## [Title]\n\n### Introduction\n\n### Main Content\n\n### Call to Action"
    })
