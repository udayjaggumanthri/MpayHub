## mPayHub Frontend

React frontend for the mPayHub platform.

## Requirements

- Node.js 18+ (recommended)
- npm 9+

## Setup

1) Install dependencies:

```bash
npm install
```

2) Create env file:

```bash
copy .env.example .env
```

3) Start development server:

```bash
npm start
```

App URL: `http://localhost:3000`

## Environment Variables

- `REACT_APP_API_BASE_URL`: backend API base URL  
  Example: `http://localhost:8000/api`

## Scripts

- `npm start`: run dev server
- `npm test`: run tests
- `npm run build`: create production build
- `npm run eject`: eject CRA config (irreversible)

## Build for Production

```bash
npm run build
```

Generated output is in `build/`.
