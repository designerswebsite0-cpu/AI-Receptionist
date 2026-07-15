# functions.md
# Resort AI Receptionist - Functions

> Status: Living Specification
> Business Domain: Luxury 5-Star Resort (first business implementation of the platform)
> Relationship to architecture.md: sections 1–27 below are the **Business Tool
> Layer** — concrete tool calls owned by the Business Action Engine and other
> engines (Conversation, Customer 360, Knowledge). Sections 28–30 (AI
> Intelligence Layer, RAG Knowledge Domains, Guest Memory) are the **AI
> reasoning layer** that decides *when* and *whether* to call those tools —
> see architecture.md §4.4 for the 8-step reasoning pipeline these compose
> into. The AI must never treat this document's business tools as a
> substitute for that reasoning pipeline, and must never invent data a
> function below was meant to supply.

Version: 1.0

This document defines every function available to the Resort AI Receptionist.

The AI should never invent data.
Whenever information requires backend verification, the AI must call the appropriate function.

---

# 1. Resort Information

## get_resort_information()
Returns:
- Resort description
- About the resort
- Awards
- Certifications
- Property size
- Number of rooms
- Number of villas
- Number of restaurants
- Nearby attractions
- Resort map
- Contact details
- Resort policies

## get_resort_timings()
Returns:
- Check-in / Check-out
- Reception
- Restaurant timings
- Spa timings
- Pool timings
- Gym timings
- Activity timings
- Kids Club
- Bar timings

## get_contact_information()
Returns:
- Phone
- Email
- WhatsApp
- Address
- GPS location
- Emergency contacts

---

# 2. Room Management

## search_rooms()
Search using:
- Check-in / Check-out
- Adults / Children
- Budget
- Room Type
- View
- Amenities

## get_room_details(room_id)
Returns:
- Description
- Images
- Videos
- Floor plan
- Area
- View
- Occupancy
- Amenities
- Price
- Availability

## compare_rooms(room_ids)
Compare multiple rooms.

## check_room_availability()
Checks live availability.

## recommend_room()
Suggests the best room based on guest preferences.

---

# 3. Reservations

- create_booking()
- modify_booking()
- cancel_booking()
- extend_booking()
- shorten_booking()
- retrieve_booking()
- resend_booking_confirmation()

---

# 4. Restaurants

- get_restaurants()
- get_restaurant_menu()
- reserve_restaurant_table()
- modify_restaurant_reservation()
- cancel_restaurant_reservation()

---

# 5. Room Service

- place_room_service_order()
- modify_room_service_order()
- cancel_room_service_order()
- track_room_service_order()

---

# 6. Activities

- get_activities()
- get_activity_details(activity_id)
- reserve_activity()
- modify_activity_booking()
- cancel_activity()

---

# 7. Spa

- get_spa_services()
- book_spa()
- modify_spa_booking()
- cancel_spa_booking()

---

# 8. Events

- get_event_information()
- inquire_event()
- schedule_event_consultation()

---

# 9. Housekeeping

- request_housekeeping()
- track_housekeeping_request()

---

# 10. Maintenance

- request_maintenance()
- track_maintenance_request()

---

# 11. Concierge

- get_local_recommendations()
- book_transport()
- book_local_tour()

---

# 12. Billing

- get_current_bill()
- get_invoice()
- split_bill()
- make_payment()
- process_refund()

---

# 13. Guest Profile

- get_guest_profile()
- update_guest_preferences()

---

# 14. Loyalty Program

- get_membership_details()
- redeem_loyalty_points()

---

# 15. Special Requests

- create_special_request()

Examples:
- Birthday decoration
- Honeymoon setup
- Proposal setup
- Wheelchair
- Baby cot

---

# 16. Complaints

- register_complaint()
- track_complaint()

---

# 17. Lost & Found

- report_lost_item()
- check_lost_item_status()

---

# 18. Feedback

- submit_feedback()
- request_feedback()

---

# 19. Notifications

- send_guest_notification()

Examples:
- Booking confirmation
- Payment updates
- Activity reminders
- Check-in reminder
- Check-out reminder

---

# 20. Emergency

- contact_emergency_services()

---

# 21. Human Escalation

- transfer_to_human()

Reasons:
- User requested
- Low AI confidence
- VIP handling
- Complaint escalation

---

# 22. Knowledge Base

- search_knowledge_base()
- search_faq()
- get_policy()
- get_current_offers()

---

# 23. Multi-language

- translate_response()

---

# 24. Conversation Memory

- get_conversation_memory()
- update_conversation_memory()

---

# 25. CRM

- create_lead()
- update_guest_record()

---

# 26. Analytics

- log_interaction()
- log_guest_intent()

---

# 27. Authentication

- verify_guest_identity()

Methods:
- OTP
- Booking ID
- Phone
- Email

Required before:
- Booking changes
- Payments
- Refunds
- Personal information


---

# 28. AI Intelligence Layer

> These are AI capabilities, not direct backend API calls.

## Intent Understanding
- detect_guest_intent()
- classify_multi_intent()
- resolve_follow_up_intent()
- detect_small_talk()
- detect_booking_intent()
- detect_sales_opportunity()

## Entity Extraction
- extract_guest_entities()
Extracts:
- Guest Name
- Phone
- Email
- Check-in / Check-out
- Adults / Children
- Budget
- Room Preference
- View Preference
- Occasion
- Dietary Preferences
- Accessibility Needs
- Language
- Transportation Details

## Conversation State
- get_conversation_state()
- update_conversation_state()
States (canonical list — matches the Phase 2 conversation state engine,
`conversations.current_state` in database.md, and architecture.md §4.4):
- Greeting
- Discovering Needs
- Collecting Information
- Recommending
- Booking
- Waiting
- Confirmation
- Upselling
- Support
- Escalation
- Closed

## AI Decision Engine
- generate_personalized_recommendation()
- suggest_best_next_action()
- detect_missing_information()
- validate_booking_flow()

## Recommendation Engine
- recommend_rooms()
- recommend_packages()
- recommend_restaurants()
- recommend_activities()
- recommend_spa_services()
- recommend_local_experiences()

## Emotional Intelligence
- detect_guest_sentiment()
- adapt_response_tone()
- identify_vip_guest()
- detect_urgent_situation()

## Sales Intelligence
- detect_upsell_opportunity()
- recommend_cross_sell_services()
- recommend_special_packages()

## Operational Intelligence
- detect_schedule_conflicts()
- suggest_alternative_slots()
- validate_operational_constraints()

## AI Handoff Intelligence
- evaluate_handoff_requirement()
- summarize_conversation_for_staff()

---

# 29. RAG Knowledge Domains

The AI can retrieve information from:
- Rooms
- Restaurants
- Menus
- Spa
- Activities
- Resort Policies
- FAQs
- Nearby Attractions
- Maps
- Events
- Seasonal Offers
- Brochures
- Images
- Videos
- SOPs
- Emergency Procedures

---

# 30. Guest Memory

- store_guest_memory()
- retrieve_guest_memory()
- update_guest_profile_memory()

Stores:
- Preferences
- Previous Visits
- Favourite Rooms
- Favourite Activities
- Dietary Preferences
- Celebrations
- Communication Preferences


---

END OF FUNCTIONS
