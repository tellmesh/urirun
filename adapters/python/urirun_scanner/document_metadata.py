from __future__ import annotations

try:
    # prefer the separately-installed package (dev/connector installs)
    from urirun_connector_scanner.document_metadata import *  # noqa: F401, F403
    from urirun_connector_scanner.document_metadata import (  # noqa: F401
        _LLM_DOC_TYPES,
        _LLM_FIELDS_SPEC,
        _coerce_amount,
        _document_type,
        _extract_document_metadata,
        _llm_api_key_ref,
        _llm_complete_metadata,
        _llm_env_file,
        _llm_extract_metadata,
        _llm_model,
        _load_env_file,
        _local_image_ocr,
        _local_image_ocr_llm,
        _local_image_ocr_tesseract,
        _normalize_llm_doc_fields,
        _normalized_document_text,
        _ocr_connector_envelope,
        _ocr_text_ok,
        _parse_amount,
        _parse_contractor,
        _parse_document_date,
        _parse_llm_json_object,
        _truthy_env,
    )
except ImportError:
    # Bundled fallback — same implementation, kept in sync with urirun-connector-scanner
    # Author: Tom Sapletta · https://tom.sapletta.com
    # Part of the ifURI solution.
    """Document OCR + LLM metadata extraction for the host dashboard scanner pipeline."""
    import json
    import os
    import re
    import time
    import unicodedata
    from datetime import date
    from pathlib import Path
    from typing import Any

    try:
        from docid.dedup import normalize_text as _dedup_normalize_text
    except Exception:  # noqa: BLE001
        _dedup_normalize_text = None

    from .document_sync import truthy_env as _truthy_env

    def _local_image_ocr_tesseract(path: str) -> dict:
        if not shutil_which("tesseract"):
            return {"ok": False, "backend": "none", "error": "tesseract is not installed on host"}
        import subprocess

        proc = subprocess.run(["tesseract", path, "stdout", "-l", "eng+pol"],
                              capture_output=True, text=True, timeout=90, check=False)
        if proc.returncode != 0:
            proc = subprocess.run(["tesseract", path, "stdout"],
                                  capture_output=True, text=True, timeout=90, check=False)
        if proc.returncode != 0:
            return {"ok": False, "backend": "tesseract", "error": (proc.stderr or "").strip()}
        text = proc.stdout.strip()
        return {"ok": True, "backend": "tesseract", "text": text, "chars": len(text)}

    def _ocr_text_ok(result: dict | None) -> bool:
        """True when an OCR result envelope actually carries usable (non-blank) text."""
        return bool(result and result.get("ok") and str(result.get("text") or "").strip())

    def _ocr_connector_envelope(path: str, backend: str) -> tuple[dict | None, dict | None]:
        """Run the urirun-connector-ocr read."""
        try:
            from urirun_connector_ocr.core import image_text  # type: ignore
        except Exception as exc:  # noqa: BLE001
            result = _local_image_ocr_tesseract(path)
            result.setdefault("connectorError", f"urirun-connector-ocr unavailable: {exc}")
            return None, result
        try:
            envelope = image_text(image=path, backend=backend, lang="eng+pol", max_chars=20000)
        except Exception as exc:  # noqa: BLE001
            result = _local_image_ocr_tesseract(path)
            result.setdefault("connectorError", str(exc))
            return None, result
        return envelope, None

    def _local_image_ocr(path: str, backend: str | None = None) -> dict:
        """OCR a scanned image for the phone-scanner pipeline."""
        backend = str(backend if backend is not None else os.environ.get("URIRUN_SCANNER_OCR_BACKEND", "auto")).strip().lower()
        if backend in {"", "tesseract"}:
            return _local_image_ocr_tesseract(path)
        envelope, finished = _ocr_connector_envelope(path, backend)
        if finished is not None:
            return finished
        if _ocr_text_ok(envelope):
            return {
                "ok": True,
                "backend": envelope.get("backend", backend),
                "text": str(envelope.get("text") or ""),
                "chars": envelope.get("chars") or len(str(envelope.get("text") or "")),
                "boxCount": envelope.get("box_count"),
                "docPreprocess": envelope.get("docPreprocess"),
            }
        fallback = _local_image_ocr_tesseract(path)
        if _ocr_text_ok(fallback):
            return fallback
        llm = _local_image_ocr_llm(path)
        if _ocr_text_ok(llm):
            return llm
        if not fallback.get("ok"):
            fallback.setdefault("connectorError", str(envelope.get("error") or "connector OCR returned no text"))
        return fallback

    def _llm_ocr_check_prerequisites(path: str) -> tuple | None:
        """Return (model, key_ref) when OCR-LLM is configured and the image is present, else None."""
        if not (path and Path(str(path)).is_file()):
            return None
        model = _llm_model(vision=True)
        if not model:
            return None
        key_ref = _llm_api_key_ref()
        if model.startswith("openrouter/") and not key_ref:
            return None
        return model, key_ref

    def _llm_ocr_import_complete():
        """Import and return the LLM complete() callable, or None when unavailable."""
        try:
            from urirun_connector_llm.core import complete  # type: ignore
            return complete
        except Exception:  # noqa: BLE001
            return None

    def _llm_ocr_call_complete(complete_fn, model: str, key_ref: str, path: str) -> dict | None:
        """Invoke LLM vision OCR and return a result envelope, or None on failure."""
        prompt = (
            "Przepisz CAŁY tekst z tego paragonu/faktury dokładnie tak jak widać, linia po linii. "
            "Zwróć wyłącznie tekst, bez komentarzy."
        )
        try:
            res = complete_fn(prompt, model=model, image=str(path), api_key=key_ref, secret_allow=key_ref)
        except Exception:  # noqa: BLE001
            return None
        if not isinstance(res, dict) or not res.get("ok"):
            return None
        text = str(res.get("response") or "").strip()
        if not text:
            return None
        return {"ok": True, "backend": "llm-vision", "text": text, "chars": len(text), "model": model}

    def _local_image_ocr_llm(path: str) -> dict | None:
        """OCR an image with a vision LLM — the final fallback when paddle and tesseract fail."""
        if not _truthy_env("URIRUN_SCANNER_OCR_LLM_FALLBACK", "1"):
            return None
        creds = _llm_ocr_check_prerequisites(path)
        if creds is None:
            return None
        complete_fn = _llm_ocr_import_complete()
        if complete_fn is None:
            return None
        model, key_ref = creds
        return _llm_ocr_call_complete(complete_fn, model, key_ref, path)

    def _normalized_document_text(text: str) -> str:
        if _dedup_normalize_text is not None:
            return _dedup_normalize_text(text)
        folded = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")
        folded = re.sub(r"[^a-zA-Z0-9.,:/@+\- ]+", " ", folded.lower())
        return re.sub(r"\s+", " ", folded).strip()


    normalized_document_text = _normalized_document_text  # public alias used by document_sync


    def _parse_document_date(text: str, fallback: str | None = None) -> str:
        candidates: list[date] = []
        for year, month, day in re.findall(r"(?<!\d)(20\d{2})[-./](\d{1,2})[-./](\d{1,2})(?!\d)", text):
            try:
                candidates.append(date(int(year), int(month), int(day)))
            except ValueError:
                pass
        for day, month, year in re.findall(r"(?<!\d)(\d{1,2})[-./](\d{1,2})[-./](20\d{2})(?!\d)", text):
            try:
                candidates.append(date(int(year), int(month), int(day)))
            except ValueError:
                pass
        if candidates:
            return min(candidates).isoformat()
        if fallback:
            match = re.search(r"(20\d{2}-\d{2}-\d{2})(?!\d)", fallback)
            if match:
                return match.group(1)
        return time.strftime("%Y-%m-%d", time.gmtime())

    def _parse_amount(text: str) -> dict:
        amount_re = re.compile(r"(?<!\d)(\d{1,3}(?:[  ]?\d{3})*(?:[,.]\d{2})|\d+[,.]\d{2})(?!\d)")
        keyword_re = re.compile(r"(razem|suma|do zaplaty|do zapłaty|naleznosc|należność|total|kwota|brutto)", re.I)
        date_context_re = re.compile(r"\b(data|date|godzina|hour|czas|time)\b", re.I)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        matches: list[tuple[int, float, str]] = []
        for idx, line in enumerate(lines):
            has_amount_keyword = bool(keyword_re.search(line))
            if date_context_re.search(line) and not has_amount_keyword:
                continue
            for raw in amount_re.findall(line):
                normalized = raw.replace(" ", "").replace(" ", "").replace(",", ".")
                try:
                    value = float(normalized)
                except ValueError:
                    continue
                score = 10 if has_amount_keyword else 0
                matches.append((score + idx, value, raw))
        if not matches:
            return {"amount": "", "currency": ""}
        best = max(matches, key=lambda item: (item[0], item[1]))
        return {"amount": f"{best[1]:.2f}", "currency": "PLN"}

    def _document_type(text: str) -> str:
        lower = text.lower()
        if "paragon" in lower or "fiskal" in lower or "receipt" in lower:
            return "paragon"
        if "faktura" in lower or "invoice" in lower or ("nip" in lower and "vat" in lower):
            return "faktura"
        if "rachunek" in lower or "bill" in lower:
            return "rachunek"
        payment_terms = ("contactless", "terminal", "karta", "kart", "obciazyc", "obciążyć", "eplatnosci", "epłatności")
        if any(term in lower for term in payment_terms):
            return "potwierdzenie"
        return "dokument"

    def _score_contractor_candidate(
        idx: int, line: str, ignored: "re.Pattern[str]", terminal_noise: "re.Pattern[str]"
    ) -> int | None:
        """Score a candidate contractor line; return None when the line should be skipped."""
        if len(line) < 3 or len(line) > 70 or ignored.search(line):
            return None
        if terminal_noise.search(line):
            return None
        if not re.search(r"[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]", line):
            return None
        digit_ratio = sum(ch.isdigit() for ch in line) / max(1, len(line))
        if digit_ratio > 0.35:
            return None
        score = 100 - idx
        if re.search(r"\b(sp\.?|s\.a\.|s\.c\.|ltd|gmbh|inc|allegro|amazon|google|openai|microsoft|apple)\b", line, re.I):
            score += 30
        if line.upper() == line and len(line) >= 5:
            score += 8
        return score

    def _parse_contractor(text: str) -> str:
        ignored = re.compile(
            r"^(faktura|paragon|rachunek|invoice|receipt|nip|vat|data|date|razem|suma|total|do zap|sprzedawca|nabywca|lp\.?|ilosc|ilość|cena|kwota|sprzedaz|sprzedaż)\b",
            re.I,
        )
        terminal_noise = re.compile(
            r"\b(pos\s*id|mid|aid|wazna\s*do|ważna\s*do|contactless|visa|uisa|mastercard|"
            r"polskie\s+e\s*p?[łl]atnosci|e\s*p?[łl]atnosci|podpis|autoryzacji|kod\s+autoryzacji)\b",
            re.I,
        )
        candidates: list[tuple[int, str]] = []
        for idx, raw in enumerate(text.splitlines()[:30]):
            line = re.sub(r"\s+", " ", raw.strip(" \t:-")).strip()
            score = _score_contractor_candidate(idx, line, ignored, terminal_noise)
            if score is not None:
                candidates.append((score, line))
        if not candidates:
            return "kontrahent-nieznany"
        return max(candidates, key=lambda item: item[0])[1]

    _LLM_DOC_TYPES = ("paragon", "faktura", "rachunek", "potwierdzenie", "dokument")

    def _load_env_file(path: Path) -> dict[str, str]:
        """Minimal KEY=VALUE .env reader (ignores comments / blanks / `export `)."""
        values: dict[str, str] = {}
        try:
            for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                if line.startswith("export "):
                    line = line[len("export "):]
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key:
                    values[key] = val
        except OSError:
            return {}
        return values

    def _llm_env_file() -> Path | None:
        """The .env that carries LLM config/credentials, if present."""
        candidates: list[Path] = []
        explicit = os.environ.get("URIRUN_LLM_ENV_FILE")
        if explicit:
            candidates.append(Path(explicit).expanduser())
        try:
            candidates.append(Path(__file__).resolve().parents[5] / "examples" / ".env")
        except IndexError:
            pass
        candidates.append(Path("~/.urirun/llm.env").expanduser())
        for path in candidates:
            if path.is_file():
                return path
        return None

    def _llm_model(*, vision: bool = False) -> str:
        """Resolve the LLM model name (config, not a secret)."""
        if vision and os.environ.get("URIRUN_SCANNER_LLM_VISION_MODEL"):
            return os.environ["URIRUN_SCANNER_LLM_VISION_MODEL"].strip()
        model = (os.environ.get("URIRUN_SCANNER_LLM_MODEL") or os.environ.get("LLM_MODEL") or "").strip()
        if model:
            return model
        env_file = _llm_env_file()
        if env_file:
            return str(_load_env_file(env_file).get("LLM_MODEL", "")).strip()
        return ""

    def _llm_api_key_ref() -> str:
        """Return the API key as a *secret reference*, never the value."""
        explicit = os.environ.get("URIRUN_SCANNER_LLM_API_KEY_REF")
        if explicit:
            return explicit.strip()
        if os.environ.get("OPENROUTER_API_KEY"):
            return "getv://OPENROUTER_API_KEY"
        env_file = _llm_env_file()
        if env_file and "OPENROUTER_API_KEY" in _load_env_file(env_file):
            return f"secret://dotenv/{env_file}#OPENROUTER_API_KEY"
        return ""

    def _coerce_amount(value: object) -> str:
        """Normalise an LLM-supplied amount to ``NNN.NN`` (or '' when not a number)."""
        if value is None:
            return ""
        raw = str(value).strip()
        if not raw:
            return ""
        raw = raw.replace(" ", "").replace(" ", "")
        raw = re.sub(r"[^0-9,.\-]", "", raw)
        if "," in raw and "." in raw:
            raw = raw.replace(".", "").replace(",", ".") if raw.rfind(",") > raw.rfind(".") else raw.replace(",", "")
        else:
            raw = raw.replace(",", ".")
        try:
            return f"{float(raw):.2f}"
        except ValueError:
            return ""

    _LLM_FIELDS_SPEC = (
        "Zwróć WYŁĄCZNIE obiekt JSON, bez komentarzy, z polami:\n"
        '{"type": jeden z ["paragon","faktura","rachunek","potwierdzenie","dokument"],\n'
        ' "date": data wystawienia/sprzedaży dokumentu w formacie YYYY-MM-DD (NIE dzisiejsza data),\n'
        ' "contractor": nazwa sprzedawcy/firmy (nie etykieta "Sprzedawca"),\n'
        ' "amount": kwota DO ZAPŁATY / SUMA / RAZEM jako liczba z kropką (np. "200.62"),\n'
        ' "currency": kod waluty ISO np. "PLN",\n'
        ' "nip": NIP sprzedawcy (same cyfry) lub "",\n'
        ' "number": numer dokumentu/faktury/paragonu lub ""}\n'
        "Gdy pola nie ma w dokumencie, użyj pustego stringa. Nie zgaduj daty — jeśli brak, zwróć \"\".\n"
    )

    def _llm_extract_metadata(ocr_text: str, *, captured_at: str | None = None,
                              image_path: str | None = None) -> dict | None:
        """Extract structured document fields with an LLM."""
        if not _truthy_env("URIRUN_SCANNER_LLM_EXTRACT", "1"):
            return None
        text = (ocr_text or "").strip()
        use_vision = bool(
            _truthy_env("URIRUN_SCANNER_LLM_VISION", "0")
            and image_path
            and Path(str(image_path)).is_file()
        )
        if not use_vision and len(text) < 8:
            return None
        model = _llm_model(vision=use_vision)
        if not model:
            return None
        key_ref = _llm_api_key_ref()
        if model.startswith("openrouter/") and not key_ref:
            return None
        res = _llm_complete_metadata(model, key_ref, text, use_vision=use_vision, image_path=image_path)
        data = _parse_llm_json_object(res)
        if data is None:
            return None
        return _normalize_llm_doc_fields(data, model=model, use_vision=use_vision)

    def _llm_complete_metadata(model: str, key_ref: str | None, text: str, *,
                               use_vision: bool, image_path: str | None) -> dict | None:
        """Call the LLM connector (vision or text mode) and return its raw response envelope."""
        try:
            from urirun_connector_llm.core import complete  # type: ignore
        except Exception:  # noqa: BLE001
            return None
        if use_vision:
            prompt = f"Przeanalizuj zdjęcie polskiego paragonu lub faktury i wyciągnij dane. {_LLM_FIELDS_SPEC}"
            if text:
                prompt += f"\nPomocniczy tekst z OCR (może zawierać błędy, zweryfikuj ze zdjęciem):\n{text[:3000]}"
            try:
                return complete(prompt, model=model, image=str(image_path), api_key=key_ref, secret_allow=key_ref)
            except Exception:  # noqa: BLE001
                return None
        prompt = (
            "Jesteś ekstraktorem danych z polskich paragonów i faktur. Poniżej tekst z OCR "
            f"(zachowana kolejność linii). {_LLM_FIELDS_SPEC}"
            f"\nTEKST OCR:\n{text[:6000]}"
        )
        try:
            return complete(prompt, model=model, api_key=key_ref, secret_allow=key_ref)
        except Exception:  # noqa: BLE001
            return None

    def _parse_llm_json_object(res: Any) -> dict | None:
        """Pull the JSON object out of an LLM completion envelope (strips ```json fences)."""
        if not isinstance(res, dict) or not res.get("ok"):
            return None
        raw = str(res.get("response") or "").strip()
        if not raw:
            return None
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.S)
        if fenced:
            raw = fenced.group(1)
        else:
            brace = re.search(r"\{.*\}", raw, re.S)
            if brace:
                raw = brace.group(0)
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return None
        return data if isinstance(data, dict) else None

    def _normalize_doc_type(type_raw: object) -> str:
        """Return the doc type when it is one of the known LLM doc types, else ''."""
        doc_type = str(type_raw or "").strip().lower()
        if doc_type not in _LLM_DOC_TYPES:
            return ""
        return doc_type

    def _normalize_doc_date(date_str: str) -> str:
        """Validate and return the date string, or '' when it does not parse as a real date."""
        if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", date_str):
            return ""
        try:
            date.fromisoformat(date_str)
        except ValueError:
            return ""
        return date_str

    def _normalize_doc_amount_currency(amount_raw: object, currency_raw: object) -> tuple[str, str]:
        """Coerce amount and currency; default currency to PLN when amount is present."""
        amount = _coerce_amount(amount_raw)
        currency = re.sub(r"[^A-Za-z]", "", str(currency_raw or "")).upper()[:3]
        if amount and not currency:
            currency = "PLN"
        return amount, currency

    def _normalize_llm_doc_fields(data: dict, *, model: str, use_vision: bool) -> dict:
        """Coerce/validate the LLM's raw fields into the canonical document-metadata shape."""
        doc_type = _normalize_doc_type(data.get("type"))
        date_val = _normalize_doc_date(str(data.get("date") or "").strip())
        contractor = re.sub(r"\s+", " ", str(data.get("contractor") or "").strip())
        if len(contractor) > 70:
            contractor = contractor[:70].strip()
        amount, currency = _normalize_doc_amount_currency(data.get("amount"), data.get("currency"))
        nip = re.sub(r"\D", "", str(data.get("nip") or ""))
        number = re.sub(r"\s+", " ", str(data.get("number") or "").strip())[:40]
        return {
            "type": doc_type,
            "date": date_val,
            "contractor": contractor,
            "amount": amount,
            "currency": currency,
            "nip": nip,
            "number": number,
            "model": model,
            "mode": "vision" if use_vision else "text",
        }

    def _apply_llm_meta_overrides(meta: dict, llm: dict) -> None:
        """Merge LLM-extracted fields into the regex-based meta dict in place."""
        for key in ("type", "contractor", "amount", "currency", "date"):
            value = str(llm.get(key) or "").strip()
            if not value:
                continue
            if key == "type" and value == "dokument" and meta["type"] != "dokument":
                continue
            if key == "contractor" and value.lower() in {"kontrahent-nieznany", "sprzedawca", "sprzedauca"}:
                continue
            meta[key] = value
        for extra in ("nip", "number"):
            if str(llm.get(extra) or "").strip():
                meta[extra] = str(llm[extra]).strip()
        meta["metaSource"] = "llm"
        meta["llmModel"] = llm.get("model", "")
        meta["llmMode"] = llm.get("mode", "text")

    def _extract_document_metadata(ocr_text: str, *, captured_at: str | None = None,
                                   image_path: str | None = None, use_llm: bool = True) -> dict:
        amount = _parse_amount(ocr_text)
        meta = {
            "type": _document_type(ocr_text),
            "date": _parse_document_date(ocr_text, captured_at),
            "contractor": _parse_contractor(ocr_text),
            "amount": amount["amount"],
            "currency": amount["currency"],
            "metaSource": "regex",
        }
        llm = _llm_extract_metadata(ocr_text, captured_at=captured_at, image_path=image_path) if use_llm else None
        if llm:
            _apply_llm_meta_overrides(meta, llm)
        return meta

    def shutil_which(binary: str) -> str | None:
        import shutil
        return shutil.which(binary)
