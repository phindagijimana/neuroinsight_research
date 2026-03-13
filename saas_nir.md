# NIR SaaS Plan

This document describes a future Software-as-a-Service (SaaS) model for NeuroInsight Research (NIR), with emphasis on security requirements for sensitive neuroimaging data.

## Purpose

- Define how NIR can be offered as a hosted SaaS platform.
- Specify security controls needed before production launch.
- Clarify shared responsibility between NIR and customer organizations.

## SaaS Scope (Future State)

Hosted NIR SaaS includes:

- multi-tenant or single-tenant control plane
- user and organization management
- connector management (HPC/remote/Pennsieve/XNAT)
- job orchestration and monitoring
- transfer orchestration and audit logs
- billing, licensing, and entitlement services

Compute execution can remain:

- customer-hosted (HPC/on-prem)
- NIR-managed workers (optional later phase)

## Recommended SaaS Architecture

## Control Plane

- API + frontend behind a secure ingress
- authentication and authorization service
- PostgreSQL for metadata
- Redis for queue/cache
- object store for artifacts and reports
- centralized logging and audit pipeline

## Execution Plane

- isolated worker runtime for jobs
- per-job sandbox boundaries
- optional connector gateways for customer HPC networks

## Tenant Isolation Model

Choose one:

- single-tenant deployments for high-security institutions
- hardened multi-tenant with strict logical isolation

Isolation controls:

- tenant-scoped RBAC
- tenant-scoped storage prefixes/buckets
- tenant-scoped encryption keys (preferred)
- strict API authorization checks on every request

## Security Baseline (Must-Have)

## Identity and Access

- SSO support (OIDC/SAML)
- MFA enforcement (at least for admin roles)
- least-privilege RBAC with clear role definitions
- SCIM/automated user provisioning (enterprise)

## Encryption

- TLS 1.2+ in transit for all external and internal service traffic
- encryption at rest for DB, object storage, backups, and logs
- managed key service (KMS) with key rotation policy

## Network Security

- private subnets for data stores
- deny-by-default security groups and network policies
- bastion/VPN/identity-aware access for admin endpoints
- WAF and DDoS protections for internet-facing endpoints

## Secrets Management

- no plaintext secrets in source code, images, or persistent config
- use secret manager with rotation and access audit
- short-lived tokens where possible

## Application Security

- secure session handling and CSRF protections
- request validation and strict input sanitization
- file upload protections (size/type/path controls)
- signed artifact verification for worker images

## Runtime and Supply Chain

- pinned container digests
- SBOM generation and dependency scanning
- image vulnerability scanning and patch SLAs
- signed release artifacts and update provenance

## Audit and Monitoring

- immutable audit logs for auth, access, transfer, and job actions
- centralized SIEM-compatible logs
- alerting on suspicious patterns (auth anomalies, privilege escalations)
- traceability from user action to infrastructure event

## Backup, Recovery, and Resilience

- encrypted automated backups
- documented RPO/RTO targets
- regular restore tests
- multi-AZ/HA posture for control plane components

## Privacy and Compliance Readiness

For sensitive/clinical environments, prepare:

- Data Processing Agreement (DPA)
- Business Associate Agreement (BAA) path if HIPAA use is expected
- subprocessor inventory and data flow diagrams
- retention and deletion policy with customer controls
- incident response and breach notification workflow

## Shared Responsibility Model

NIR SaaS provider responsibilities:

- control plane security and operations
- identity, authorization, and tenant isolation enforcement
- patching, logging, monitoring, and incident response
- backup and disaster recovery execution

Customer responsibilities:

- correct user role assignment and approvals
- endpoint security for client machines
- data governance classification and permitted use
- security posture of external compute and storage they connect

## Commercialization Considerations

## Packaging

- Starter: hosted control plane + standard connectors
- Pro: advanced transfers, operational analytics, priority support
- Enterprise: SSO/SCIM, advanced audit export, policy controls, SLA, optional dedicated tenant

## Pricing Drivers

- users/seats
- number of active projects/tenants
- managed compute minutes (if applicable)
- data transfer/storage usage
- support and compliance tier

## Security as a Product Feature

Communicate clearly:

- where data is stored
- how it is encrypted
- who can access it
- how long it is retained
- what audit data customers can export

## Rollout Roadmap (Suggested)

## Stage A: Foundation

- define SaaS target architecture
- implement robust RBAC and org model
- centralize audit events and log pipeline

## Stage B: Security Hardening

- SSO/MFA rollout
- secrets manager + rotation
- vulnerability management automation
- incident response runbooks and drills

## Stage C: Compliance and Contracts

- DPA templates and legal review
- BAA process (if needed)
- security documentation package for procurement

## Stage D: Limited Release

- pilot institutions under controlled onboarding
- SLA and support process validation
- penetration test and remediation

## Stage E: General Availability

- production launch with tiered plans
- ongoing quarterly security reviews and annual penetration testing

## Go-Live Security Checklist

- [ ] Threat model completed and reviewed
- [ ] SSO/MFA available
- [ ] RBAC tested for tenant boundary enforcement
- [ ] Secrets manager in place with rotation
- [ ] Encryption at rest and in transit validated
- [ ] Audit logs immutable and exportable
- [ ] Backup/restore tested in staging
- [ ] Incident response tabletop completed
- [ ] Security documentation published
- [ ] External penetration test completed

## Operational KPIs (Security and Trust)

- mean time to patch critical vulnerabilities
- failed login and privilege escalation events
- tenant isolation test pass rate
- restore success rate and recovery time
- SLA uptime and incident response time

## Notes

Until SaaS launch maturity is reached, continue recommending Linux self-hosted deployment for production-sensitive workloads, with macOS as orchestrator where appropriate.
