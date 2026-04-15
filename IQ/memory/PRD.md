# DUX IQ - Merchant Payment Dashboard

## Overview
A merchant payment dashboard mobile app built with React Native / Expo. Frontend-only with all mock data — no backend or LLM integration.

## Features
- **Merchant Header**: Displays merchant name (Barista Coffee), MID (98234100001), TID (EP0000001)
- **4 KPI Cards**: Total Sales Today, Total Transactions, Pending Settlement, Last Payout
- **Last Payout Details**: Dark card with amount, date, and action buttons
- **Transaction List**: With filter tabs (All, Sales, Void, Refund, Pending)
- **Bottom Tab Navigation**: Dashboard, Transactions, Settlements, Profile
- **DUX IQ Chat Modal**: AI copilot for settlement queries with:
  - Proactive suggestion chips
  - Settlement Q&A flow
  - "Did this resolve your issue?" flow
  - Support ticket creation (ticket ID format: ICICIDDMMYYHHMMSS00001)
  - Star rating for support experience

## Tech Stack
- React Native / Expo SDK 54
- Expo Router (file-based routing with tabs)
- All data mocked in `/src/data/mockData.ts`
- No backend dependencies

## Data Source
All data is **MOCKED** in the frontend. No backend API calls are made.
