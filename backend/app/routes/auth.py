"""Registration and login endpoints."""

from __future__ import annotations

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from db import queries

from ..auth import create_token, hash_password, verify_password
from ..dependencies import get_db_conn

router = APIRouter(prefix="/api/auth")


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=30, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(..., min_length=6)


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/register", status_code=201)
async def register(
    body: RegisterRequest,
    db: aiosqlite.Connection = Depends(get_db_conn),
) -> dict:
    if await queries.get_user_by_username(db, body.username):
        raise HTTPException(status_code=409, detail="Username already taken")
    user = await queries.create_user(db, body.username, hash_password(body.password))
    return {
        "token": create_token(user["id"]),
        "user_id": user["id"],
        "username": body.username,
    }


@router.post("/login")
async def login(
    body: LoginRequest,
    db: aiosqlite.Connection = Depends(get_db_conn),
) -> dict:
    user = await queries.get_user_by_username(db, body.username)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return {
        "token": create_token(user["id"]),
        "user_id": user["id"],
        "username": body.username,
    }
