# Insighta Labs — Intelligence Query Engine

A FastAPI + PostgreSQL API for querying demographic profiles with advanced filtering, sorting, pagination, and natural-language search.

---

## Quick Start

### 1. Clone & install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set environment variable

```bash
cp .env.example .env
# Edit .env and set your DATABASE_URL
```

### 3. Seed the database

```bash
python seed.py profiles_seed.json
```

Re-running is safe — duplicate names are silently skipped.

### 4. Start the server

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Deploying to Render

1. Create a **PostgreSQL** database on Render and copy the internal connection string.
2. Create a **Web Service** pointing to this repo.
3. Set the environment variable `DATABASE_URL` to the connection string from step 1.
4. Set the **Start Command** to:
   ```
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```
5. After deploy, run the seed script once via the Render shell:
   ```bash
   python seed.py profiles_seed.json
   ```

---

## Endpoints

### `GET /api/profiles`

Fetch profiles with optional filtering, sorting, and pagination.

**Query Parameters**

| Parameter               | Type   | Default      | Description                                     |
|-------------------------|--------|--------------|-------------------------------------------------|
| `gender`                | string | —            | `male` or `female`                              |
| `age_group`             | string | —            | `child`, `teenager`, `adult`, `senior`          |
| `country_id`            | string | —            | ISO 3166-1 alpha-2 code (e.g. `NG`, `KE`)       |
| `min_age`               | int    | —            | Minimum age (inclusive)                         |
| `max_age`               | int    | —            | Maximum age (inclusive)                         |
| `min_gender_probability`| float  | —            | Minimum gender confidence score (0–1)           |
| `min_country_probability`| float | —            | Minimum country confidence score (0–1)          |
| `sort_by`               | string | `created_at` | `age`, `created_at`, or `gender_probability`    |
| `order`                 | string | `asc`        | `asc` or `desc`                                 |
| `page`                  | int    | `1`          | Page number (min: 1)                            |
| `limit`                 | int    | `10`         | Results per page (min: 1, max: 50)              |

**Example**
```
GET /api/profiles?gender=male&country_id=NG&min_age=25&sort_by=age&order=desc&page=1&limit=10
```

---

### `GET /api/profiles/search`

Natural-language query endpoint. Converts plain English into filters.

**Query Parameters**

| Parameter | Type   | Description                          |
|-----------|--------|--------------------------------------|
| `q`       | string | Plain-English query (required)        |
| `page`    | int    | Page number (default: 1)             |
| `limit`   | int    | Results per page (default: 10, max 50)|
| `sort_by` | string | Same options as `/api/profiles`      |
| `order`   | string | `asc` or `desc`                      |

**Example**
```
GET /api/profiles/search?q=young males from nigeria
```

---

## Natural Language Parsing

### How it works

The parser (`services/nlp_parser.py`) uses regex pattern matching against a lowercase version of the query. It extracts up to three kinds of filters independently — gender, age, and country — and ANDs them together. No AI or external LLM is used.

---

### Supported keywords and their mappings

#### Gender

| Keywords | Maps to |
|---|---|
| `male`, `males`, `man`, `men`, `boy`, `boys` | `gender=male` |
| `female`, `females`, `woman`, `women`, `girl`, `girls` | `gender=female` |
| Both male AND female words present | No gender filter applied |

#### Age groups (stored values)

| Keywords | Maps to |
|---|---|
| `child`, `children`, `kid`, `kids` | `age_group=child` |
| `teenager`, `teen`, `teens`, `adolescent` | `age_group=teenager` |
| `adult`, `adults` | `age_group=adult` |
| `senior`, `seniors`, `elderly` | `age_group=senior` |

#### Special age keyword

| Keyword | Maps to |
|---|---|
| `young` | `min_age=16`, `max_age=24` (not a stored age_group) |

#### Age comparisons (numeric)

| Pattern | Maps to |
|---|---|
| `above X` / `over X` / `older than X` / `at least X` | `min_age=X` |
| `below X` / `under X` / `younger than X` / `at most X` | `max_age=X` |
| `between X and Y` | `min_age=X`, `max_age=Y` |
| `aged X` / `age X` | `min_age=X`, `max_age=X` |

Age comparison values **override** the `young` bounds when both appear. For example, `young males above 18` → `min_age=18, max_age=24`.

#### Country

Country names and common demonyms (e.g. "nigerian", "kenyan") are matched anywhere in the query. Multi-word country names (e.g. "south africa", "burkina faso") are checked before single-word ones to prevent partial matches.

```
"from nigeria"        → country_id=NG
"in kenya"            → country_id=KE
"nigerian adults"     → country_id=NG + age_group=adult
"people from angola"  → country_id=AO
```

Supported countries include all 54 African Union member states plus major global countries (US, UK, France, Germany, Brazil, India, China, Japan, Canada, Australia).

---

### Worked examples

| Query | Extracted filters |
|---|---|
| `young males from nigeria` | `gender=male, min_age=16, max_age=24, country_id=NG` |
| `females above 30` | `gender=female, min_age=30` |
| `people from angola` | `country_id=AO` |
| `adult males from kenya` | `gender=male, age_group=adult, country_id=KE` |
| `male and female teenagers above 17` | `age_group=teenager, min_age=17` |
| `elderly women in ghana` | `gender=female, age_group=senior, country_id=GH` |
| `children below 10` | `age_group=child, max_age=10` |

---

### Uninterpretable queries

If zero filters are extracted, the endpoint returns:

```json
{ "status": "error", "message": "Unable to interpret query" }
```

Examples of uninterpretable queries: `"hello"`, `"xyz123"`, `"show me everything"` (no gender, age, or country keywords).

---

## Limitations

1. **"young" is not additive with age groups.** A query like `"young adults"` will set both `age_group=adult` and `min_age=16, max_age=24`. This may return an empty result if the data's adult age range doesn't overlap with 16–24.

2. **No multi-gender targeting.** Queries like `"males and females over 30"` drop the gender filter and return all genders above 30. There is no OR-based filtering across gender values.

3. **No compound country queries.** `"people from nigeria and ghana"` only picks up the first matched country.

4. **No negation.** `"not from nigeria"` or `"males except seniors"` are not supported.

5. **No fuzzy matching.** Misspellings like `"nigerria"` or `"femalle"` will not be recognised.

6. **Demonym coverage is incomplete.** Some rare demonyms (e.g. "ivorian" for Côte d'Ivoire) may not be in the mapping table. The full country name always works.

7. **Context words are ignored.** Words like `"show"`, `"find"`, `"give me"`, `"all"`, `"some"` are safely ignored — the parser only looks for its keyword patterns.

8. **No relative age terms beyond "young".** Terms like `"middle-aged"`, `"grown-up"`, or `"toddler"` are not mapped to any filter.

---

## Error Reference

| Code | Meaning |
|---|---|
| 400 | Missing or empty parameter / invalid parameter value |
| 422 | Invalid parameter type (e.g. `page=abc`) |
| 422 | Unable to interpret NL query |
| 500 | Internal server error |

All errors follow:
```json
{ "status": "error", "message": "<description>" }
```

---

## Database Schema

```sql
CREATE TABLE profiles (
    id                  UUID PRIMARY KEY,
    name                VARCHAR UNIQUE NOT NULL,
    gender              VARCHAR NOT NULL,
    gender_probability  FLOAT NOT NULL,
    age                 INT NOT NULL,
    age_group           VARCHAR NOT NULL,
    country_id          VARCHAR(2) NOT NULL,
    country_name        VARCHAR NOT NULL,
    country_probability FLOAT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL
);
```

All IDs use **UUID v7** (RFC 9562) — time-ordered, generated in Python without external libraries.
