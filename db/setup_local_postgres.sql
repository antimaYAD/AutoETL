-- Run this once, as the postgres superuser, to create the AutoETL app
-- database and a dedicated (non-superuser) login role for it.
--
-- From PowerShell:
--   & "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -h localhost -f db\setup_local_postgres.sql
-- (it will prompt for the postgres superuser password)
--
-- Change the password below before running, then put the same value in
-- your .env DATABASE_URL.

CREATE USER autoetl WITH PASSWORD 'change-me';
CREATE DATABASE autoetl OWNER autoetl;
GRANT ALL PRIVILEGES ON DATABASE autoetl TO autoetl;
