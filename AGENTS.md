# Contexto do Projeto: Clima-Zap (APIEXT III)

## 📌 Visão Geral

Sistema de monitoramento e alertas climáticos para a região do Cariri, consumindo a API aberta Open-Meteo e disponibilizando dados via API REST para uma interface Web SPA e integração com mensageria.

## 🛠️ Stack Tecnológica

- **Frontend:** React.js (construído com Vite), estilização em Sass (SCSS modular), hospedagem na Vercel.
- **Backend:** Python 3.10+ com FastAPI, Pydantic v2, Uvicorn, hospedagem no Render.
- **Banco de Dados:** PostgreSQL (hospedado via Neon ou Supabase).
- **APIs Externas:** Open-Meteo API (sem necessidade de API Key).

## 📐 Padrões de Código e Regras

1. **FastAPI:**
   - Use rotas assíncronas (`async def`).
   - Separe a lógica em camadas: `routers`, `services` e `models/schemas`.
   - Utilize `httpx` para chamadas assíncronas a APIs externas.
2. **React + SCSS:**
   - Componentes funcionais com Hooks (`useState`, `useEffect`).
   - Crie folhas de estilo modulares (ex: `Header.module.scss`) e reutilize variáveis globais (`_variables.scss`).
   - Requisições HTTP centralizadas via `fetch` nativo ou instância do `axios`.
