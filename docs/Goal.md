# Goal.md
# AI Receptionist Platform Product Goal

> Living Product Specification

## Vision

Build a production-grade, multi-tenant AI Receptionist platform that unifies:

- WhatsApp
- Website Live Chat
- AI Voice Calls

Customers should experience one intelligent receptionist regardless of the channel they use.

---

# Current Business Implementation: Luxury 5-Star Resort

This is not a generic chatbot demo. The platform's first real business
implementation is an AI Receptionist for a **luxury 5-star resort**, covering
rooms, villas, restaurants, bars, cafés, pools, spa & wellness, gym, kids
club, activities, conference rooms, wedding venues, banquet halls, event
spaces, concierge, transportation, local experiences, housekeeping,
maintenance, billing, loyalty, and guest profiles.

The AI must behave like a highly trained luxury front-desk executive, not a
FAQ bot: natural, context-aware, capable of multi-intent conversations,
personalized recommendations, tasteful upselling, sentiment-aware tone, and
sensible escalation — never inventing availability, prices, or policy.

The concrete business tool catalog for this vertical lives in
[functions.md](functions.md); every architecture decision here must remain
generic enough that a future non-resort tenant only needs a different
`functions.md` and knowledge base, not a different platform.

Active channels: **WhatsApp** and **Website Chat** only. Voice remains a
later roadmap phase (Phase 9) — do not build voice features yet.

---

# Core Objectives

The platform should:

- Answer customer questions accurately
- Understand business knowledge
- Book appointments and reservations
- Capture and qualify leads
- Handle customer support
- Personalize every interaction
- Work alongside human staff
- Scale across multiple businesses
- Be secure by default

---

# Customer 360

Customer 360 is the heart of the platform.

Each customer profile should include:

- Identity
- Communication preferences
- Favourite products
- Favourite services
- Preferred timings
- Behaviour patterns
- Purchase history
- Booking history
- Call history
- Chat history
- Staff notes
- Customer value score
- VIP status
- AI-generated customer summary

The same profile must be shared between chat and voice.

---

# Omnichannel Experience

The AI should remember information across channels.

Example:

WhatsApp →
Customer prefers evening appointments.

Later...

Phone Call →
AI already knows the customer's preferred time.

No duplicated customer records should exist.

---

# Chatbot Capabilities

The chatbot should:

- Answer FAQs
- Search business knowledge
- Recommend products/services
- Create bookings
- Modify bookings
- Cancel bookings
- Capture leads
- Create support tickets
- Generate payment links
- Share files and menus
- Handle attachments
- Escalate to humans
- Continue conversations naturally

---

# Voice Receptionist Goals

Future voice support should provide:

- Natural conversations
- Real-time responses
- Customer personalization
- Booking assistance
- Lead qualification
- Support requests
- Call recording
- Call transcripts
- Shared Customer 360

---

# Human Handoff

Conversation modes:

- AI_ACTIVE
- HUMAN_ACTIVE
- AI_ASSIST
- WAITING_FOR_CUSTOMER
- RESOLVED
- BLOCKED

Humans and AI must collaborate seamlessly.

---

# Dashboard Goals

Provide:

- Real-time inbox
- Customer profiles
- Customer 360
- Analytics
- AI controls
- Human takeover
- Call history
- Chat history
- Booking management
- Lead management
- Staff management

---

# AI Principles

The AI should:

- Never hallucinate business information.
- Use Customer 360 naturally.
- Ask for clarification when needed.
- Prefer backend tools over guessing.
- Escalate when confidence is low.

---

# Technical Goals

Current target scale:

- 100–500 conversations/day
- 100–500 calls/day

Architecture goals:

- Modular monolith
- Multi-tenant
- API-first
- AI-first
- Secure by default
- Ready for future scaling

---

# Success Criteria

The platform is successful when:

- Businesses trust it to communicate with customers.
- Customer conversations feel personal.
- Staff can intervene instantly.
- Customer 360 improves every interaction.
- Calls and chats share one unified backend.
- The platform is reliable, secure, and maintainable.

---

# Long-Term Vision

Become a complete AI front-desk platform for businesses by expanding to:

- Instagram
- Facebook Messenger
- Telegram
- Email
- Outbound AI calling
- CRM automation
- Advanced analytics
- White-label SaaS
- Enterprise deployments

Every future feature should strengthen the unified AI Receptionist rather than create separate products.
