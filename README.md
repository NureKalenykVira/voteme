# VoteMe

Blockchain-oriented web platform for organizing and conducting electronic votings with cryptographic verification and public result auditability.  
The project demonstrates end-to-end full-stack development: Angular SPA, REST API, PostgreSQL, Solidity smart contract, and Merkle-proof-based vote verification.

**Live:** [voteme-frontend.onrender.com](https://voteme-frontend.onrender.com) · **API docs:** [voteme-backend.onrender.com/docs](https://voteme-backend.onrender.com/docs#/)

---

## Tech Stack

![Angular](https://img.shields.io/badge/Angular-DD0031?style=for-the-badge&logo=angular&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white)
![SCSS](https://img.shields.io/badge/SCSS-CC6699?style=for-the-badge&logo=sass&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Solidity](https://img.shields.io/badge/Solidity-363636?style=for-the-badge&logo=solidity&logoColor=white)
![Ethereum](https://img.shields.io/badge/Ethereum_Sepolia-3C3C3D?style=for-the-badge&logo=ethereum&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)

---

## About the Project

**VoteMe** is a web platform for organizing transparent and verifiable electronic votings.  
The backend is built with Python and FastAPI and exposes REST endpoints for voting management, authentication, blockchain interaction, and audit logging.  
The frontend is an Angular SPA with separate flows for voters, organizers, and administrators.

Any voter can independently verify that their vote was counted — without trusting the platform — using a Merkle proof and the Etherscan transaction of the finalization event.

---

## Functional Overview

### Voter side
- Join a voting via invite code or QR link
- Three-step voting flow with confirmation
- Cryptographic receipt with commitment hash
- Self-service vote verification via Merkle proof and Etherscan

### Organizer side
- Create and configure votings
- Invite voters via QR code, unique code, or CSV upload
- Monitor participation in real time
- Access results dashboard with vote distribution and activity timeline

### Auditor side
- Access audit log for assigned votings
- Verify hash chain integrity of voting events
- View blockchain records and commitment details

### Admin side
- User and voting management
- Platform-wide statistics with interactive charts
- Full audit log with hash chain integrity status

---

## Backend Architecture

The FastAPI backend follows a layered service-based architecture:

- `app/api` — dependencies and route registration
- `app/services` — business logic (Auth, Voting, Vote, Admin, Audit, Email, Blockchain, FSM)
- `app/repositories` — SQLAlchemy ORM data access
- `app/models` — SQLAlchemy models
- `app/schemas` — Pydantic request/response schemas
- `app/blockchain` — Web3.py client and VoteRegistry contract interface
- `app/scheduler` — background voting state machine scheduler
- `app/middleware` — maintenance mode middleware
- `app/core` — config, security, enums, Cloudinary client
- `app/utils` — Merkle tree utilities

A single SQLAlchemy session factory is created at startup and injected via FastAPI dependencies.  
Database migrations are managed with **Alembic**.

---

## Blockchain Module

Smart contract: **VoteRegistry** (Solidity), deployed on **Ethereum Sepolia testnet**.  
Backend interaction via **Web3.py** over JSON-RPC.

On-chain data per voting:
- Commitment hashes for each vote (keccak256 of `voting_id + user_hash + option_id + nonce`)
- Merkle root at finalization

The smart contract does not store who voted for what — only commitments. After finalization, any voter can reconstruct the Merkle root from their commitment, nonce, and proof, and compare it against the on-chain value.

---

## Repository Structure

        voteme/
          frontend/               # Angular SPA
            src/app/
              core/               # guards, interceptors, services
              features/           # auth, elections, vote, admin, audit, profile, ...
              shared/             # ui components, layout, validators
          backend/                # FastAPI backend
            app/
              api/                # deps, route registration
              services/           # business logic
              repositories/       # data access (SQLAlchemy)
              models/             # DB models
              schemas/            # Pydantic schemas
              blockchain/         # Web3.py + VoteRegistry ABI
              scheduler/          # voting state machine scheduler
              middleware/         # maintenance mode
              core/               # config, security, enums
              utils/              # Merkle tree
            alembic/              # DB migrations
            tests/                # pytest test suite
          contracts/              # Solidity smart contract + Hardhat
          docker-compose.yml
          README.md

---

## Getting Started (Development)

### Backend
        cd backend
        cp .env.example .env
        pip install -r requirements.txt
        uvicorn app.main:app --reload

Backend will be available at http://localhost:8000.  
API docs (Swagger UI) at http://localhost:8000/docs.

### Frontend
        cd frontend
        npm install
        npm start

Frontend will be available at http://localhost:4200.

### Smart Contract (local)
        cd contracts
        npm install
        npx hardhat test

---

## API Overview

Full interactive API documentation (Swagger UI) is available at:  
[voteme-backend.onrender.com/docs](https://voteme-backend.onrender.com/docs#/)

---

## Testing

| Layer | Tool | Coverage |
|-------|------|----------|
| Backend | pytest | 215 tests, 65% coverage |
| Smart contract | Hardhat | 3 tests (publish, vote, finalize) |
| Frontend | Vitest | 60 tests |
| Load testing | Locust | 50 concurrent users, 0 errors, median 220ms |

---

## Project Status

Core functionality is implemented and fully operational:
- full voting lifecycle management with state machine
- cryptographic commitment scheme and Merkle-proof verification
- blockchain finalization on Ethereum Sepolia
- hash chain audit log with tamper detection
- Angular SPA with voter, organizer, and admin flows
- email notifications via Gmail API with SMTP fallback
- Deployment on Render

Planned improvements:
- migration to Ethereum mainnet
- mobile application
