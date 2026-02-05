# Project Context: TechFlow Analytics Platform

This document contains institutional knowledge for the TechFlow project. Reference this when making decisions.

## Product Overview

TechFlow is a B2B analytics platform for mid-market SaaS companies (50-500 employees). We help product teams understand user behavior, identify churn risks, and optimize onboarding flows.

**Founded:** 2022  
**Current ARR:** $2.4M  
**Team size:** 18 (8 engineering, 4 product, 3 sales, 3 ops)  
**Primary market:** US, expanding to EU in Q3

## Technical Architecture

### Current Stack
- **Backend:** Python 3.11, FastAPI, PostgreSQL 15, Redis
- **Frontend:** React 18, TypeScript, TailwindCSS
- **Infrastructure:** AWS (EKS, RDS, ElastiCache, S3)
- **Data pipeline:** Apache Kafka → Spark → Snowflake
- **Auth:** Auth0 (SSO for enterprise tier)

### Known Technical Debt
1. **Event ingestion bottleneck** – Single Kafka partition for small customers causing delays during peak (9-11am EST)
2. **Dashboard query performance** – Some complex dashboards timeout at 30s; need query optimization or pre-aggregation
3. **Mobile SDK gap** – React Native SDK exists but iOS/Android native SDKs requested by 3 enterprise prospects

### Recent Decisions
- **2024-01 Decision:** Chose Snowflake over BigQuery for data warehouse (better SQL compatibility, customer preference)
- **2024-02 Decision:** Delayed mobile native SDKs to prioritize EU data residency (GDPR compliance deadline)
- **2024-03 Decision:** Adopted OpenTelemetry for internal observability (replacing Datadog to reduce costs)

## Customer Segments

### Tier 1: Startup ($299/mo)
- Up to 50K MAU
- 7-day data retention
- Email support only
- ~180 customers, 12% monthly churn

### Tier 2: Growth ($999/mo)
- Up to 500K MAU
- 90-day data retention
- Slack support, 24h response SLA
- ~45 customers, 4% monthly churn

### Tier 3: Enterprise ($3,500+/mo)
- Unlimited MAU
- 2-year data retention
- Dedicated CSM, SSO, custom integrations
- ~12 customers, <1% annual churn

## Key Stakeholders

- **Sarah Chen (CEO):** Focus on enterprise expansion, wants to double enterprise tier by EOY
- **Marcus Webb (CTO):** Concerned about technical debt, pushing for platform stability sprint
- **Priya Sharma (VP Product):** Prioritizing self-serve analytics builder (top feature request)
- **James Liu (VP Sales):** Needs native mobile SDKs for 2 pending enterprise deals worth $180K ARR

## Competitive Landscape

| Competitor | Strength | Weakness | Our Advantage |
|------------|----------|----------|---------------|
| Amplitude | Brand, features | Expensive, complex | Simpler UX, faster TTV |
| Mixpanel | Self-serve | Slow support | Better enterprise features |
| Heap | Auto-capture | Data quality issues | Manual instrumentation = cleaner data |
| PostHog | Open source | Limited scale | Managed service, no DevOps needed |

## Pending Decisions (Need Input)

1. **Mobile SDK prioritization** – Build native iOS/Android or improve React Native? James needs answer by April 15.
2. **EU infrastructure** – Single EU region (Frankfurt) or multi-region? Cost difference is $4K/mo.
3. **Pricing restructure** – Startup tier has high churn; consider usage-based or raise floor?

## Q2 OKRs

**O1: Accelerate enterprise pipeline**
- KR1: Close 5 new enterprise deals ($200K new ARR)
- KR2: Reduce enterprise sales cycle from 68 to 45 days
- KR3: Launch 2 enterprise-only features

**O2: Improve platform reliability**
- KR1: 99.9% uptime (currently 99.7%)
- KR2: P95 dashboard load time under 3s (currently 4.2s)
- KR3: Zero customer-reported data loss incidents

**O3: Prepare EU expansion**
- KR1: EU data residency certified by June 30
- KR2: First 3 EU customers onboarded
- KR3: GDPR compliance audit passed
