from __future__ import annotations

import io
import os
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from comercial import render_commercial_page as render_commercial_sector
from comercial import render_registry_page as render_registry_sector
from preenchimento import render_preparation_editor as render_preparation_sector
from revisao import render_review_page as render_review_sector
from supabase import Client, create_client


CLIENT_COLUMNS = [
    "CPF",
    "NOME",
    "Grupo",
    "Reunião",
    "Nivel de Complexidade",
    "Status Preenchimento",
    "Responsável pelo Preenchimento",
    "Status Pós-Envio",
    "Telefone",
    "Senha Gov",
    "Cadastro de Procuração",
]

DOCUMENT_COLUMNS = [
    "Nome Pessoa",
    "Tipo Documento",
    "Instituição",
    "Status",
    "Última Atualização",
    "chave_controle",
]

PREPARATION_STEPS = [
    ("cadastro", "Informações cadastrais, permanece?"),
    ("bens_direitos", "Bens e direitos, permanece?"),
    ("dividas_emprestimos", "Possui dívidas, AFAC ou empréstimos?"),
]

DOCUMENT_TYPE_OPTIONS = [
    "Despesas Dedutíveis",
    "Informe de Rendimentos",
    "Informes Bancários",
]

DOCUMENT_STATUS_OPTIONS = [
    "PENDENTE",
    "RECEBIDO",
    "SOLICITAR DOCUMENTO",
    "SEM STATUS",
]

TEAM_FALLBACK = [
    {
        "name": "Wanessa",
        "display_name": "Wanessa",
        "email": "wanessa.aparecida@gestaocontabil.com",
        "role": "comercial",
        "allowed_sectors": "Comercial,Preenchimento,Revisão",
        "can_manage_records": True,
        "permission_level": "full",
    },
    {
        "name": "Paulo",
        "display_name": "Paulo",
        "email": "paulo.nunes@gestaocontabil.com",
        "role": "preenchimento",
        "allowed_sectors": "Comercial,Preenchimento,Revisão,Cadastros",
        "can_manage_records": True,
        "permission_level": "full",
    },
    {
        "name": "Valdivone",
        "display_name": "Valdivone",
        "email": "valdivone.dias@gestaocontabil.com",
        "role": "preenchimento",
        "allowed_sectors": "Preenchimento,Revisão",
        "can_manage_records": True,
        "permission_level": "full",
    },
    {
        "name": "Michelle",
        "display_name": "Michelle",
        "email": "michelle.mustafa@gestaocontabil.com",
        "role": "preenchimento",
        "allowed_sectors": "Preenchimento,Revisão",
        "can_manage_records": True,
        "permission_level": "full",
    },
    {
        "name": "Erlane",
        "display_name": "Erlane",
        "email": "",
        "role": "preenchimento",
        "allowed_sectors": "Preenchimento",
        "can_manage_records": False,
        "permission_level": "full",
    },
    {
        "name": "Heverton",
        "display_name": "Heverton",
        "email": "heverton@gestaocontabil.com",
        "role": "revisao",
        "allowed_sectors": "Comercial,Preenchimento,Revisão,Cadastros",
        "can_manage_records": True,
        "permission_level": "full",
    },
    {
        "name": "Duda",
        "display_name": "Duda",
        "email": "maria.lins@gestaocontabil.com",
        "role": "preenchimento",
        "allowed_sectors": "Preenchimento",
        "can_manage_records": False,
        "permission_level": "status_only",
    },
    {
        "name": "Malu",
        "display_name": "Malu",
        "email": "maria.luiza@gestaocontabil.com",
        "role": "preenchimento",
        "allowed_sectors": "Preenchimento",
        "can_manage_records": False,
        "permission_level": "status_only",
    },
    {
        "name": "Renato",
        "display_name": "Renato",
        "email": "renato@gestaocontabil.com",
        "role": "revisao_final",
        "allowed_sectors": "Comercial,Preenchimento,Revisão",
        "can_manage_records": True,
        "permission_level": "full",
    },
]

STATUS_OPTIONS = [
    "PENDENTE",
    "PRONTO PARA PREENCHER",
    "EM PREENCHIMENTO",
    "PRONTO PARA REVISÃO",
    "AJUSTE - HEVERTON",
    "AGUARDANDO REUNIÃO",
    "TRANSMITIDO",
    "SEM STATUS",
]

AVAILABLE_DECLARATION_STATUSES = {"PENDENTE", "SEM STATUS", "PRONTO PARA PREENCHER"}
SECTOR_OPTIONS = ["Comercial", "Preenchimento", "Revisão", "Cadastros"]
PREPARATION_QUEUE_READY_STATUS = "Pronta para Preenchimento"
PREPARATION_QUEUE_WAITING_STATUS = "Aguardando documentação"
STATUS_PROGRESS_MAP = {
    "PENDENTE": 0,
    "SEM STATUS": 0,
    "PRONTO PARA PREENCHER": 10,
    "EM PREENCHIMENTO": 25,
    "PRONTO PARA REVISÃO": 55,
    "AJUSTE - HEVERTON": 85,
    "TRANSMITIDO": 100,
    "AGUARDANDO REUNIÃO": 100,
}

STAGE_CHECKPOINTS = {
    "EM PREENCHIMENTO": {
        "step_key": "etapa_em_preenchimento",
        "step_label": "Declaração foi para preenchimento",
        "date_column": "Data foi para preenchimento",
    },
    "PRONTO PARA REVISÃO": {
        "step_key": "etapa_pronto_revisao",
        "step_label": "Declaração chegou para revisão",
        "date_column": "Data chegou para revisão",
    },
    "AJUSTE - HEVERTON": {
        "step_key": "etapa_ajuste_heverton",
        "step_label": "Declaração foi para ajuste",
        "date_column": "Data foi para ajuste",
    },
    "TRANSMITIDO": {
        "step_key": "etapa_transmitido",
        "step_label": "Declaração transmitida",
        "date_column": "Data transmissão",
    },
    "AGUARDANDO REUNIÃO": {
        "step_key": "etapa_aguardando_reuniao",
        "step_label": "Declaração aguardando reunião",
        "date_column": "Data aguardando reunião",
    },
}
STAGE_DATE_COLUMNS = [config["date_column"] for config in STAGE_CHECKPOINTS.values()]

LOCAL_CLIENT_SAMPLE = Path(r"C:\Users\user\Downloads\INFORMAÇÕES DE CLIENTES(Relatório) (8).csv")
LOCAL_DOCUMENT_SAMPLE = Path(r"C:\Users\user\Downloads\controle_documento(Controle Documentos (2)).csv")
DATA_DIR = Path(__file__).resolve().parent / "data"
SNAPSHOT_PATH = DATA_DIR / "historico_snapshots.csv"
SUPABASE_CREDS_PATH = DATA_DIR / "supabase-credentials.txt"
LOGO_PATH = Path(__file__).resolve().parent / "logogestao.png"
BUNDLE_CACHE_TTL_SECONDS = 20

STANDARD_IMPORT_COLUMNS = [
    "NOME",
    "CPF",
    "Grupo",
    "Reunião",
    "Nivel de Complexidade",
    "Status Preenchimento",
    "Responsável pelo Preenchimento",
    "Status Pós-Envio",
    "Telefone",
    "Senha Gov",
    "Cadastro de Procuração",
    "Tipo Documento",
    "Instituição",
    "Status Documento",
    "Última Atualização",
    "chave_controle",
]

CLIENT_IMPORT_UPDATE_FIELDS = [
    "Grupo",
    "Reunião",
    "Nivel de Complexidade",
    "Status Preenchimento",
    "Responsável pelo Preenchimento",
    "Status Pós-Envio",
    "CPF",
    "Telefone",
    "Senha Gov",
    "Cadastro de Procuração",
]

DOCUMENT_IMPORT_UPDATE_FIELDS = [
    "Status Documento",
    "Última Atualização",
    "chave_controle",
]


def normalize_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\n", " ")).strip()


def normalize_key(value: object) -> str:
    text = normalize_text(value).upper()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^A-Z0-9]+", " ", text).strip()


def normalize_column(value: object) -> str:
    return normalize_key(value).lower()


def normalize_digits(value: object) -> str:
    return "".join(char for char in normalize_text(value) if char.isdigit())


def normalize_cpf(value: object) -> str:
    digits = normalize_digits(value)
    if not digits:
        return ""
    digits = digits.zfill(11)
    if len(digits) != 11:
        return digits
    return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"


def normalize_phone(value: object) -> str:
    digits = normalize_digits(value)
    if not digits:
        return ""
    if len(digits) == 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
    if len(digits) == 11:
        return f"({digits[:2]}) {digits[2]} {digits[3:7]}-{digits[7:]}"
    return digits


def split_gov_access(value: object) -> tuple[str, bool]:
    text = normalize_text(value)
    if not text:
        return "", False
    if "CERTIFICADO DIGITAL" in normalize_key(text):
        return "", True
    return text, False


def safe_percent(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return round((numerator / denominator) * 100, 1)


def documentation_hint(value: object) -> str:
    normalized = normalize_key(value)
    if "RECEBIDO TOTAL" in normalized:
        return "Recebido total"
    if "RECEBIDO PARCIAL" in normalized:
        return "Recebido parcial"
    if "SEM DOCUMENTACAO" in normalized:
        return "Sem documentação"
    return ""


def canonical_status(value: object) -> str:
    text = normalize_text(value).upper()
    normalized = normalize_key(text)
    if documentation_hint(text):
        return "PENDENTE"
    if "TRANSMITID" in normalized:
        return "TRANSMITIDO"
    if "REVISAO" in normalized and "RENATO" in normalized:
        return "PRONTO PARA REVISÃO"
    if "PREENCHIMENTO" in normalized:
        return "EM PREENCHIMENTO"
    if "PENDENTE" in normalized:
        return "PENDENTE"
    if "AJUSTE" in normalized:
        return text
    return text or "SEM STATUS"


def documentation_status(total: int, received: int) -> str:
    if total == 0 or received == 0:
        return "Sem documentação"
    if received == total:
        return "Recebido total"
    return "Recebido parcial"


def is_ready_for_preparation(total: int, received: int) -> bool:
    if total <= 0:
        return False
    return safe_percent(received, total) > 75


def preparation_queue_status(total: int, received: int) -> str:
    return (
        PREPARATION_QUEUE_READY_STATUS
        if is_ready_for_preparation(total, received)
        else PREPARATION_QUEUE_WAITING_STATUS
    )


def is_unassigned_preparer(value: object) -> bool:
    return normalize_key(value) in {"", "NAO ATRIBUIDO"}


def build_available_preparation_queue(people_df: pd.DataFrame) -> pd.DataFrame:
    if people_df.empty:
        return people_df.copy()
    return people_df[
        (people_df["% documentação recebida"] > 75)
        & people_df["Status Preenchimento"].isin(sorted(AVAILABLE_DECLARATION_STATUSES))
        & people_df["Responsável pelo Preenchimento"].map(is_unassigned_preparer)
    ].copy()


def status_progress_percent(status_value: object) -> int:
    return STATUS_PROGRESS_MAP.get(normalize_text(status_value).upper(), 0)


def list_join(values: pd.Series) -> str:
    cleaned = [normalize_text(value) for value in values if normalize_text(value)]
    return "\n".join(dict.fromkeys(cleaned))


def document_description_with_note(description: object, note: object) -> str:
    description_text = normalize_text(description)
    note_text = normalize_text(note)
    if note_text:
        return f"{description_text} | Obs: {note_text}"
    return description_text


def is_bank_document(document_type: str, institution: str) -> bool:
    text = normalize_key(f"{document_type} {institution}")
    bank_terms = [
        "BANCO",
        "ITAU",
        "BRADESCO",
        "SANTANDER",
        "CAIXA",
        "NUBANK",
        "NU PAGAMENTOS",
        "SICOOB",
        "SICREDI",
        "XP",
        "BTG",
        "INTER",
        "C6",
        "MERCADO PAGO",
        "RICO",
        "CLEAR",
        "GENIAL",
        "SOFISA",
        "ORIGINAL",
        "BMG",
        "SAFRA",
        "PAN",
        "COOPERATIVA",
        "CORRETORA",
        "INVEST",
    ]
    return any(term in text for term in bank_terms)


def document_category(document_type: object, institution: object) -> str:
    doc_type = normalize_key(document_type)
    institution_key = normalize_key(institution)
    if "DESPES" in doc_type or "PAGAMENTO" in doc_type or "DEPENDENTE" in doc_type:
        return "despesas_dedutiveis"
    if is_bank_document(doc_type, institution_key):
        return "informes_bancarios"
    if "ISENT" in doc_type:
        return "renda_isenta"
    if "EXCLUS" in doc_type:
        return "tributacao_exclusiva"
    if "REND" in doc_type or "INFORMATIVO" in doc_type:
        return "renda_tributavel"
    return "outros_documentos"


SECTION_LABELS = {
    "renda_tributavel": "Fontes de renda tributáveis",
    "renda_isenta": "Rendas isentas",
    "tributacao_exclusiva": "Tributação exclusiva",
    "despesas_dedutiveis": "Pagamentos efetuados / despesas dedutíveis",
    "informes_bancarios": "Informes bancários",
    "outros_documentos": "Outros documentos",
}


def read_key_value_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.strip().startswith("-"):
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def load_supabase_public_config() -> dict[str, str]:
    file_values = read_key_value_file(SUPABASE_CREDS_PATH)
    secrets_values: dict[str, str] = {}
    try:
        secrets_values = {
            "SUPABASE_URL": st.secrets.get("SUPABASE_URL", ""),
            "NEXT_PUBLIC_SUPABASE_URL": st.secrets.get("NEXT_PUBLIC_SUPABASE_URL", ""),
            "SUPABASE_ANON_KEY": st.secrets.get("SUPABASE_ANON_KEY", ""),
            "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY": st.secrets.get("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY", ""),
        }
        if "supabase" in st.secrets:
            supabase_section = st.secrets["supabase"]
            secrets_values.update(
                {
                    "SUPABASE_URL": supabase_section.get("SUPABASE_URL", secrets_values["SUPABASE_URL"]),
                    "NEXT_PUBLIC_SUPABASE_URL": supabase_section.get(
                        "NEXT_PUBLIC_SUPABASE_URL",
                        secrets_values["NEXT_PUBLIC_SUPABASE_URL"],
                    ),
                    "SUPABASE_ANON_KEY": supabase_section.get("SUPABASE_ANON_KEY", secrets_values["SUPABASE_ANON_KEY"]),
                    "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY": supabase_section.get(
                        "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY",
                        secrets_values["NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY"],
                    ),
                }
            )
    except Exception:
        secrets_values = {}
    url = (
        os.getenv("SUPABASE_URL")
        or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
        or secrets_values.get("SUPABASE_URL")
        or secrets_values.get("NEXT_PUBLIC_SUPABASE_URL")
        or file_values.get("SUPABASE_URL")
        or file_values.get("NEXT_PUBLIC_SUPABASE_URL")
        or ""
    )
    anon_key = (
        os.getenv("SUPABASE_ANON_KEY")
        or os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
        or secrets_values.get("SUPABASE_ANON_KEY")
        or secrets_values.get("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
        or file_values.get("SUPABASE_ANON_KEY")
        or file_values.get("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
        or ""
    )
    if not url or not anon_key:
        return {}
    return {"url": url, "anon_key": anon_key}


def clear_supabase_session() -> None:
    for key in ["supabase_access_token", "supabase_refresh_token", "supabase_user_email"]:
        st.session_state.pop(key, None)


def build_supabase_client() -> Client | None:
    config = load_supabase_public_config()
    if not config:
        return None
    client = create_client(config["url"], config["anon_key"])
    access_token = st.session_state.get("supabase_access_token")
    refresh_token = st.session_state.get("supabase_refresh_token")
    if access_token and refresh_token:
        try:
            auth_response = client.auth.set_session(access_token, refresh_token)
            session = getattr(auth_response, "session", None)
            if session is not None:
                st.session_state["supabase_access_token"] = session.access_token
                st.session_state["supabase_refresh_token"] = session.refresh_token
                st.session_state["supabase_user_email"] = getattr(session.user, "email", "")
        except Exception:
            clear_supabase_session()
            return None
    return client


def invalidate_data_cache() -> None:
    st.session_state.pop("supabase_bundle_cache", None)
    st.session_state.pop("supabase_bundle_loaded_at", None)


def load_supabase_bundle_cached(client: Client) -> dict[str, pd.DataFrame]:
    cached_bundle = st.session_state.get("supabase_bundle_cache")
    loaded_at = st.session_state.get("supabase_bundle_loaded_at")
    if cached_bundle is not None and isinstance(loaded_at, datetime):
        cache_age = (datetime.now() - loaded_at).total_seconds()
        if cache_age < BUNDLE_CACHE_TTL_SECONDS:
            return cached_bundle
    bundle = load_supabase_bundle(client)
    st.session_state["supabase_bundle_cache"] = bundle
    st.session_state["supabase_bundle_loaded_at"] = datetime.now()
    return bundle


def fetch_all_rows(client: Client, table_name: str, columns: str, page_size: int = 1000) -> list[dict]:
    rows: list[dict] = []
    start = 0
    while True:
        response = client.table(table_name).select(columns).range(start, start + page_size - 1).execute()
        data = response.data or []
        rows.extend(data)
        if len(data) < page_size:
            break
        start += page_size
    return rows


def read_csv_bytes(file_bytes: bytes) -> pd.DataFrame:
    errors: list[str] = []
    for encoding in ["utf-8-sig", "utf-8", "latin1", "cp1252"]:
        try:
            return pd.read_csv(
                io.BytesIO(file_bytes),
                sep=None,
                engine="python",
                encoding=encoding,
                dtype=str,
            )
        except Exception as exc:
            errors.append(f"{encoding}: {exc}")
    raise ValueError("Não foi possível ler o CSV. Tentativas: " + " | ".join(errors))


def read_table_file(file_bytes: bytes, file_name: str) -> pd.DataFrame:
    suffix = Path(file_name).suffix.lower()
    if suffix in [".xlsx", ".xls"]:
        return pd.read_excel(io.BytesIO(file_bytes), dtype=str)
    return read_csv_bytes(file_bytes)


def select_columns(df: pd.DataFrame, expected_columns: list[str]) -> pd.DataFrame:
    normalized_to_original = {normalize_column(column): column for column in df.columns}
    selected: dict[str, pd.Series] = {}
    for expected in expected_columns:
        original = normalized_to_original.get(normalize_column(expected))
        selected[expected] = df[original] if original else pd.Series([""] * len(df))
    return pd.DataFrame(selected)


def parse_clients(file_bytes: bytes, file_name: str) -> pd.DataFrame:
    raw_df = read_table_file(file_bytes, file_name)
    df = select_columns(raw_df, CLIENT_COLUMNS)

    for column in CLIENT_COLUMNS:
        df[column] = df[column].map(normalize_text)

    gov_split = df["Senha Gov"].map(split_gov_access)
    df["CPF"] = df["CPF"].map(normalize_cpf)
    df["NOME"] = df["NOME"].replace("", "Sem nome identificado")
    df["Grupo"] = df["Grupo"].replace("", "Sem grupo")
    df["Reunião"] = df["Reunião"].replace("", "Sem reunião informada")
    df["Nivel de Complexidade"] = (
        df["Nivel de Complexidade"].str.strip().str.title().replace("", "Não informado")
    )
    df["Documentação Informada"] = df["Status Preenchimento"].map(documentation_hint)
    df["Status Preenchimento"] = df["Status Preenchimento"].map(canonical_status)
    df["Responsável pelo Preenchimento"] = (
        df["Responsável pelo Preenchimento"].str.upper().replace("", "Não atribuído")
    )
    df["Status Pós-Envio"] = df["Status Pós-Envio"].str.upper().replace("", "Não informado")
    df["Telefone"] = df["Telefone"].map(normalize_phone)
    df["Senha Gov"] = gov_split.map(lambda item: item[0])
    df["Tem Certificado Digital"] = gov_split.map(lambda item: item[1])
    df["Cadastro de Procuração"] = df["Cadastro de Procuração"].replace("", "Não informado")
    df["chave_pessoa"] = df["NOME"].map(normalize_key)
    return df


def parse_documents(file_bytes: bytes, file_name: str) -> pd.DataFrame:
    raw_df = read_table_file(file_bytes, file_name)
    df = select_columns(raw_df, DOCUMENT_COLUMNS)

    for column in DOCUMENT_COLUMNS:
        df[column] = df[column].map(normalize_text)

    df["Nome Pessoa"] = df["Nome Pessoa"].replace("", "Sem nome identificado")
    df["Tipo Documento"] = df["Tipo Documento"].replace("", "Não informado")
    df["Instituição"] = df["Instituição"].replace("", "Não informada")
    df["Status"] = df["Status"].str.upper().replace("", "SEM STATUS")
    df["Última Atualização"] = pd.to_datetime(
        df["Última Atualização"], format="%d/%m/%Y", errors="coerce"
    )
    df["documento_descricao"] = df["Tipo Documento"] + " - " + df["Instituição"]
    df["chave_pessoa"] = df["Nome Pessoa"].map(normalize_key)
    return df


def default_team_df() -> pd.DataFrame:
    return pd.DataFrame(TEAM_FALLBACK)


def parse_allowed_sectors(value: object) -> list[str]:
    sectors = [normalize_text(item) for item in normalize_text(value).split(",") if normalize_text(item)]
    return [sector for sector in SECTOR_OPTIONS if sector in sectors]


def get_user_profile(team_df: pd.DataFrame, user_email: str, source: str) -> dict[str, object]:
    if source != "Supabase":
        return {
            "email": "",
            "display_name": "Equipe",
            "allowed_sectors": ["Comercial", "Preenchimento", "Revisão"],
            "can_manage_records": False,
            "permission_level": "full",
        }
    normalized_email = normalize_text(user_email).lower()
    if normalized_email and not team_df.empty and "email" in team_df.columns:
        match = team_df[team_df["email"].map(lambda value: normalize_text(value).lower()) == normalized_email]
        if not match.empty:
            row = match.iloc[0]
            return {
                "email": normalized_email,
                "display_name": normalize_text(row.get("display_name", "")) or normalize_text(row.get("name", "")) or normalized_email,
                "allowed_sectors": parse_allowed_sectors(row.get("allowed_sectors", "")),
                "can_manage_records": bool(row.get("can_manage_records", False)),
                "permission_level": normalize_text(row.get("permission_level", "")) or "full",
            }
    return {
        "email": normalized_email,
        "display_name": normalized_email or "Usuário",
        "allowed_sectors": [],
        "can_manage_records": False,
        "permission_level": "read_only",
    }


def load_supabase_bundle(client: Client) -> dict[str, pd.DataFrame]:
    client_select_columns = (
        "id, normalized_name, full_name, group_name, meeting_status, complexity_level, tax_status, "
        "assigned_preparer, post_filing_status, preparation_queue_status, updated_at"
    )
    try:
        client_rows = fetch_all_rows(client, "clients", client_select_columns)
    except Exception as exc:
        if "preparation_queue_status" not in str(exc):
            raise
        client_rows = fetch_all_rows(
            client,
            "clients",
            "id, normalized_name, full_name, group_name, meeting_status, complexity_level, tax_status, assigned_preparer, post_filing_status, updated_at",
        )
    try:
        document_rows = fetch_all_rows(
            client,
            "documents",
            "id, client_id, document_type, institution, status, last_update, control_key, notes",
        )
    except Exception as exc:
        if "notes" not in str(exc):
            raise
        document_rows = fetch_all_rows(
            client,
            "documents",
            "id, client_id, document_type, institution, status, last_update, control_key",
        )
    private_rows = fetch_all_rows(
        client,
        "client_private",
        "client_id, cpf, phone, gov_password, has_digital_certificate, power_of_attorney",
    )
    team_rows = fetch_all_rows(
        client,
        "team_members",
        "name, display_name, email, role, allowed_sectors, can_manage_records, permission_level, active",
    )
    checkpoint_rows = fetch_all_rows(
        client,
        "declaration_checkpoints",
        "client_id, step_key, step_label, completed, note, updated_by, updated_at",
    )

    client_df = pd.DataFrame(client_rows).fillna("")
    if client_df.empty:
        clients_df = pd.DataFrame(columns=CLIENT_COLUMNS + ["Status para Preenchimento", "chave_pessoa", "client_id", "client_updated_at"])
    else:
        clients_df = pd.DataFrame(
            {
                "client_id": client_df["id"],
                "CPF": "",
                "NOME": client_df["full_name"].map(normalize_text),
                "Grupo": client_df["group_name"].map(normalize_text).replace("", "Sem grupo"),
                "Reunião": client_df["meeting_status"].map(normalize_text).replace("", "Sem reunião informada"),
                "Nivel de Complexidade": client_df["complexity_level"].map(normalize_text).replace("", "Não informado"),
                "Documentação Informada": client_df["tax_status"].map(documentation_hint),
                "Status Preenchimento": client_df["tax_status"].map(canonical_status),
                "Responsável pelo Preenchimento": client_df["assigned_preparer"].map(normalize_text).replace("", "Não atribuído"),
                "Status Pós-Envio": client_df["post_filing_status"].map(normalize_text).replace("", "Não informado"),
                "Status para Preenchimento": (
                    client_df["preparation_queue_status"].map(normalize_text)
                    if "preparation_queue_status" in client_df.columns
                    else ""
                ),
                "Telefone": "",
                "Senha Gov": "",
                "Tem Certificado Digital": False,
                "Cadastro de Procuração": "",
                "chave_pessoa": client_df["normalized_name"].map(normalize_text),
                "client_updated_at": pd.to_datetime(client_df["updated_at"], errors="coerce"),
            }
        )

    client_lookup = {
        int(row["id"]): {
            "full_name": normalize_text(row["full_name"]),
            "normalized_name": normalize_text(row["normalized_name"]),
        }
        for row in client_rows
    }

    document_source = []
    for row in document_rows:
        client_info = client_lookup.get(
            int(row["client_id"]),
            {"full_name": "Sem nome identificado", "normalized_name": ""},
        )
        document_source.append(
            {
                "document_id": int(row["id"]),
                "client_id": int(row["client_id"]),
                "Nome Pessoa": client_info["full_name"],
                "Tipo Documento": normalize_text(row.get("document_type", "")) or "Não informado",
                "Instituição": normalize_text(row.get("institution", "")) or "Não informada",
                "Status": normalize_text(row.get("status", "")).upper() or "SEM STATUS",
                "Última Atualização": pd.to_datetime(row.get("last_update"), errors="coerce"),
                "chave_controle": normalize_text(row.get("control_key", "")),
                "Observação Documento": normalize_text(row.get("notes", "")),
                "documento_descricao": (
                    f"{normalize_text(row.get('document_type', '')) or 'Não informado'} - "
                    f"{normalize_text(row.get('institution', '')) or 'Não informada'}"
                ),
                "chave_pessoa": client_info["normalized_name"] or normalize_key(client_info["full_name"]),
            }
        )
    documents_df = pd.DataFrame(document_source)
    if documents_df.empty:
        documents_df = pd.DataFrame(
            columns=DOCUMENT_COLUMNS + ["Observação Documento", "documento_descricao", "documento_descricao_com_obs", "chave_pessoa", "client_id", "document_id"]
        )
    else:
        documents_df["Observação Documento"] = documents_df["Observação Documento"].fillna("").map(normalize_text)
        documents_df["documento_descricao_com_obs"] = documents_df.apply(
            lambda row: document_description_with_note(row["documento_descricao"], row["Observação Documento"]),
            axis=1,
        )

    private_df = pd.DataFrame(private_rows).fillna("")
    if private_df.empty:
        private_df = pd.DataFrame(
            columns=["client_id", "CPF", "Telefone", "Senha Gov", "Tem Certificado Digital", "Cadastro de Procuração"]
        )
    else:
        private_df = pd.DataFrame(
            {
                "client_id": private_df["client_id"].astype(int),
                "CPF": private_df["cpf"].map(normalize_text),
                "Telefone": private_df["phone"].map(normalize_text),
                "Senha Gov": private_df["gov_password"].map(normalize_text),
                "Tem Certificado Digital": private_df["has_digital_certificate"].fillna(False).astype(bool),
                "Cadastro de Procuração": private_df["power_of_attorney"].map(normalize_text),
            }
        )

    team_df = pd.DataFrame(team_rows).fillna("")
    if team_df.empty:
        team_df = default_team_df()

    checkpoints_df = pd.DataFrame(checkpoint_rows)
    if checkpoints_df.empty:
        checkpoints_df = pd.DataFrame(
            columns=["client_id", "step_key", "step_label", "completed", "note", "updated_by", "updated_at"]
        )
    else:
        checkpoints_df["client_id"] = checkpoints_df["client_id"].astype(int)
        checkpoints_df["completed"] = checkpoints_df["completed"].fillna(False).astype(bool)
        checkpoints_df["note"] = checkpoints_df["note"].fillna("").map(normalize_text)
        checkpoints_df["updated_by"] = checkpoints_df["updated_by"].fillna("").map(normalize_text)
        checkpoints_df["updated_at"] = pd.to_datetime(checkpoints_df["updated_at"], errors="coerce")

    return {
        "clients_df": clients_df,
        "documents_df": documents_df,
        "private_df": private_df,
        "team_df": team_df,
        "checkpoints_df": checkpoints_df,
    }


def build_people_summary(clients_df: pd.DataFrame, documents_df: pd.DataFrame) -> pd.DataFrame:
    docs_by_client = (
        documents_df.groupby("chave_pessoa", dropna=False)
        .agg(
            nome_documentos=("Nome Pessoa", "first"),
            total_documentos=("Status", "size"),
            documentos_recebidos=("Status", lambda values: int((values == "RECEBIDO").sum())),
            documentos_pendentes=("Status", lambda values: int((values != "RECEBIDO").sum())),
            documentos_enviados_lista=(
                "documento_descricao_com_obs",
                lambda values: list_join(
                    documents_df.loc[values.index][
                        documents_df.loc[values.index, "Status"] == "RECEBIDO"
                    ]["documento_descricao_com_obs"]
                ),
            ),
            documentos_faltantes_lista=(
                "documento_descricao_com_obs",
                lambda values: list_join(
                    documents_df.loc[values.index][
                        documents_df.loc[values.index, "Status"] != "RECEBIDO"
                    ]["documento_descricao_com_obs"]
                ),
            ),
            ultima_atualizacao_docs=("Última Atualização", "max"),
        )
        .reset_index()
    )

    declaration_columns = [
        column
        for column in [
            "client_id",
            "CPF",
            "NOME",
            "Grupo",
            "Reunião",
            "Nivel de Complexidade",
            "Documentação Informada",
            "Status Preenchimento",
            "Status para Preenchimento",
            "Responsável pelo Preenchimento",
            "Status Pós-Envio",
            "Telefone",
            "Senha Gov",
            "Tem Certificado Digital",
            "Cadastro de Procuração",
            "chave_pessoa",
            "client_updated_at",
        ]
        if column in clients_df.columns
    ]
    people_df = clients_df[declaration_columns].copy().merge(docs_by_client, on="chave_pessoa", how="outer")
    if "client_id" not in people_df.columns:
        people_df["client_id"] = range(1, len(people_df) + 1)
    else:
        people_df["client_id"] = pd.to_numeric(people_df["client_id"], errors="coerce")
        next_id = int(people_df["client_id"].max()) if people_df["client_id"].notna().any() else 0
        missing_count = int(people_df["client_id"].isna().sum())
        if missing_count:
            people_df.loc[people_df["client_id"].isna(), "client_id"] = range(next_id + 1, next_id + missing_count + 1)
        people_df["client_id"] = people_df["client_id"].astype(int)

    people_df["NOME"] = people_df["NOME"].replace("", pd.NA).fillna(people_df["nome_documentos"])
    people_df["Grupo"] = people_df["Grupo"].fillna("Sem grupo")
    people_df["Reunião"] = people_df["Reunião"].fillna("Sem reunião informada")
    people_df["Nivel de Complexidade"] = people_df["Nivel de Complexidade"].fillna("Não informado")
    if "Documentação Informada" in people_df.columns:
        people_df["Documentação Informada"] = people_df["Documentação Informada"].fillna("")
    people_df["Status Preenchimento"] = people_df["Status Preenchimento"].fillna("SEM STATUS")
    if "Status para Preenchimento" in people_df.columns:
        people_df["Status para Preenchimento"] = people_df["Status para Preenchimento"].fillna("")
    people_df["Responsável pelo Preenchimento"] = people_df["Responsável pelo Preenchimento"].fillna("Não atribuído")

    for column in ["CPF", "Telefone", "Senha Gov", "Cadastro de Procuração"]:
        if column in people_df.columns:
            people_df[column] = people_df[column].fillna("")
    if "Tem Certificado Digital" in people_df.columns:
        people_df["Tem Certificado Digital"] = people_df["Tem Certificado Digital"].fillna(False).astype(bool)

    for column in ["total_documentos", "documentos_recebidos", "documentos_pendentes"]:
        people_df[column] = people_df[column].fillna(0).astype(int)

    people_df["Documentação"] = people_df.apply(
        lambda row: documentation_status(row["total_documentos"], row["documentos_recebidos"])
        if int(row["total_documentos"]) > 0
        else (row.get("Documentação Informada", "") or "Sem documentação"),
        axis=1,
    )
    people_df["Status para Preenchimento"] = people_df.apply(
        lambda row: preparation_queue_status(int(row["total_documentos"]), int(row["documentos_recebidos"])),
        axis=1,
    )
    people_df["% documentação recebida"] = people_df.apply(
        lambda row: safe_percent(row["documentos_recebidos"], row["total_documentos"]),
        axis=1,
    )
    people_df["Recebidos / Total"] = people_df.apply(
        lambda row: f"{int(row['documentos_recebidos'])} de {int(row['total_documentos'])}",
        axis=1,
    )
    people_df["documentos_enviados_lista"] = people_df["documentos_enviados_lista"].fillna("")
    people_df["documentos_faltantes_lista"] = people_df["documentos_faltantes_lista"].fillna("")
    people_df["documentos_faltantes_lista"] = people_df.apply(
        lambda row: "Checklist não cadastrado no banco"
        if int(row["total_documentos"]) == 0 and not row["documentos_faltantes_lista"]
        else row["documentos_faltantes_lista"],
        axis=1,
    )
    people_df["ultima_atualizacao_docs"] = pd.to_datetime(people_df["ultima_atualizacao_docs"], errors="coerce")
    if "client_updated_at" not in people_df.columns:
        people_df["client_updated_at"] = pd.NaT
    people_df["dias_desde_ultima_atualizacao"] = (
        pd.Timestamp(date.today()) - people_df["ultima_atualizacao_docs"]
    ).dt.days
    people_df["Precisa cobrar"] = (
        (people_df["Documentação"] != "Recebido total")
        & (
            people_df["ultima_atualizacao_docs"].isna()
            | (people_df["dias_desde_ultima_atualizacao"] > 7)
        )
    )
    return people_df.sort_values(["Status Preenchimento", "Grupo", "NOME"])


def attach_private_data(people_df: pd.DataFrame, private_df: pd.DataFrame) -> pd.DataFrame:
    if people_df.empty or private_df.empty or "client_id" not in people_df.columns:
        return people_df
    merged = people_df.merge(private_df, on="client_id", how="left", suffixes=("", "_private"))
    for column in ["CPF", "Telefone", "Senha Gov", "Cadastro de Procuração"]:
        if f"{column}_private" in merged.columns:
            merged[column] = merged[f"{column}_private"].replace("", pd.NA).fillna(merged[column])
            merged = merged.drop(columns=[f"{column}_private"])
    if "Tem Certificado Digital_private" in merged.columns:
        merged["Tem Certificado Digital"] = (
            merged["Tem Certificado Digital_private"].fillna(False).astype(bool)
            | merged["Tem Certificado Digital"].fillna(False).astype(bool)
        )
        merged = merged.drop(columns=["Tem Certificado Digital_private"])
    return merged


def build_checkpoint_summary(checkpoints_df: pd.DataFrame, documents_df: pd.DataFrame | None = None) -> pd.DataFrame:
    if checkpoints_df.empty:
        return pd.DataFrame(
            columns=[
                "client_id",
                "completed_steps",
                "progress_percent",
                "last_step_update",
                "Observações Gerais da Declaração",
                "BKP salvo no drive",
                "Confirmação pronta para revisão",
                *STAGE_DATE_COLUMNS,
            ]
        )

    client_ids_df = checkpoints_df[["client_id"]].drop_duplicates().copy()
    progress_keys = {step_key for step_key, _ in PREPARATION_STEPS}
    progress_df = checkpoints_df[
        checkpoints_df["step_key"].astype(str).str.startswith("doc_")
        | checkpoints_df["step_key"].isin(progress_keys)
    ].copy()

    if progress_df.empty:
        summary_df = client_ids_df.copy()
        summary_df["completed_steps"] = 0
    else:
        summary_df = (
            progress_df.groupby("client_id")
            .agg(
                completed_steps=("completed", lambda values: int(pd.Series(values).astype(bool).sum())),
            )
            .reset_index()
        )
        summary_df = client_ids_df.merge(summary_df, on="client_id", how="left")
        summary_df["completed_steps"] = summary_df["completed_steps"].fillna(0).astype(int)

    latest_update_df = (
        checkpoints_df.groupby("client_id")
        .agg(
            last_step_update=("updated_at", "max"),
        )
        .reset_index()
    )
    summary_df = summary_df.merge(latest_update_df, on="client_id", how="left")

    observation_df = checkpoints_df[checkpoints_df["step_key"] == "observacoes_gerais"].copy()
    if not observation_df.empty:
        observation_df = (
            observation_df.sort_values(["client_id", "updated_at"])
            .drop_duplicates(subset=["client_id"], keep="last")[["client_id", "note"]]
            .rename(columns={"note": "Observações Gerais da Declaração"})
        )
        summary_df = summary_df.merge(observation_df, on="client_id", how="left")
    else:
        summary_df["Observações Gerais da Declaração"] = ""

    backup_df = checkpoints_df[checkpoints_df["step_key"] == "bkp_drive"].copy()
    if not backup_df.empty:
        backup_df = (
            backup_df.sort_values(["client_id", "updated_at"])
            .drop_duplicates(subset=["client_id"], keep="last")[["client_id", "completed"]]
            .rename(columns={"completed": "BKP salvo no drive"})
        )
        summary_df = summary_df.merge(backup_df, on="client_id", how="left")
    else:
        summary_df["BKP salvo no drive"] = False

    ready_df = checkpoints_df[checkpoints_df["step_key"] == "confirmacao_pronto_revisao"].copy()
    if not ready_df.empty:
        ready_df = (
            ready_df.sort_values(["client_id", "updated_at"])
            .drop_duplicates(subset=["client_id"], keep="last")[["client_id", "completed"]]
            .rename(columns={"completed": "Confirmação pronta para revisão"})
        )
        summary_df = summary_df.merge(ready_df, on="client_id", how="left")
    else:
        summary_df["Confirmação pronta para revisão"] = False

    for config in STAGE_CHECKPOINTS.values():
        stage_df = checkpoints_df[checkpoints_df["step_key"] == config["step_key"]].copy()
        if stage_df.empty:
            summary_df[config["date_column"]] = pd.NaT
            continue
        stage_df = (
            stage_df.sort_values(["client_id", "updated_at"])
            .drop_duplicates(subset=["client_id"], keep="first")[["client_id", "updated_at"]]
            .rename(columns={"updated_at": config["date_column"]})
        )
        summary_df = summary_df.merge(stage_df, on="client_id", how="left")

    if documents_df is not None and not documents_df.empty and "client_id" in documents_df.columns:
        doc_totals = (
            documents_df.groupby("client_id")
            .size()
            .reset_index(name="document_steps")
        )
        summary_df = summary_df.merge(doc_totals, on="client_id", how="left")
        summary_df["document_steps"] = summary_df["document_steps"].fillna(0).astype(int)
    else:
        summary_df["document_steps"] = 0
    summary_df["total_steps"] = summary_df["document_steps"] + len(PREPARATION_STEPS)
    summary_df["progress_percent"] = summary_df.apply(
        lambda row: safe_percent(int(row["completed_steps"]), int(row["total_steps"])),
        axis=1,
    )
    return summary_df


def attach_progress(people_df: pd.DataFrame, checkpoint_summary_df: pd.DataFrame) -> pd.DataFrame:
    if people_df.empty:
        return people_df
    merged = people_df.copy()
    if "client_id" in merged.columns and not checkpoint_summary_df.empty:
        merged = merged.merge(checkpoint_summary_df, on="client_id", how="left")
    if "completed_steps" not in merged.columns:
        merged["completed_steps"] = 0
    merged["completed_steps"] = merged["completed_steps"].fillna(0).astype(int)
    merged["progress_percent"] = merged["Status Preenchimento"].map(status_progress_percent).astype(float)
    if "total_documentos" in merged.columns:
        fallback_total_steps = merged["total_documentos"].fillna(0).astype(int)
    else:
        fallback_total_steps = pd.Series([0] * len(merged), index=merged.index)
    if "total_steps" not in merged.columns:
        merged["total_steps"] = fallback_total_steps
    merged["total_steps"] = merged["total_steps"].fillna(fallback_total_steps).astype(int)
    if "last_step_update" not in merged.columns:
        merged["last_step_update"] = pd.NaT
    if "Observações Gerais da Declaração" not in merged.columns:
        merged["Observações Gerais da Declaração"] = ""
    merged["Observações Gerais da Declaração"] = merged["Observações Gerais da Declaração"].fillna("").map(normalize_text)
    if "BKP salvo no drive" not in merged.columns:
        merged["BKP salvo no drive"] = False
    merged["BKP salvo no drive"] = merged["BKP salvo no drive"].fillna(False).astype(bool)
    if "Confirmação pronta para revisão" not in merged.columns:
        merged["Confirmação pronta para revisão"] = False
    merged["Confirmação pronta para revisão"] = merged["Confirmação pronta para revisão"].fillna(False).astype(bool)
    if "client_updated_at" not in merged.columns:
        merged["client_updated_at"] = pd.NaT
    merged["client_updated_at"] = pd.to_datetime(merged["client_updated_at"], errors="coerce")
    merged["last_step_update"] = pd.to_datetime(merged["last_step_update"], errors="coerce")
    if "Data chegada documentação" not in merged.columns:
        merged["Data chegada documentação"] = pd.to_datetime(merged.get("ultima_atualizacao_docs", pd.NaT), errors="coerce")
    for column in STAGE_DATE_COLUMNS:
        if column not in merged.columns:
            merged[column] = pd.NaT
        merged[column] = pd.to_datetime(merged[column], errors="coerce")
    stage_fallbacks = {
        "EM PREENCHIMENTO": "Data foi para preenchimento",
        "PRONTO PARA REVISÃO": "Data chegou para revisão",
        "AJUSTE - HEVERTON": "Data foi para ajuste",
        "TRANSMITIDO": "Data transmissão",
        "AGUARDANDO REUNIÃO": "Data aguardando reunião",
    }
    for status, column in stage_fallbacks.items():
        mask = (merged["Status Preenchimento"] == status) & merged[column].isna()
        merged.loc[mask, column] = merged.loc[mask, "client_updated_at"]
    merged["last_activity_at"] = merged.apply(
        lambda row: max(
            [value for value in [row["client_updated_at"], row["last_step_update"]] if pd.notna(value)],
            default=pd.NaT,
        ),
        axis=1,
    )
    merged["Progresso Geral"] = merged["progress_percent"].map(lambda value: f"{value:.0f}%")
    return merged


def build_checkpoint_editor_state(checkpoints_df: pd.DataFrame, client_id: int) -> list[dict]:
    step_map = {}
    if not checkpoints_df.empty:
        filtered = checkpoints_df[checkpoints_df["client_id"] == client_id]
        step_map = {row["step_key"]: row for _, row in filtered.iterrows()}

    editor_state = []
    for step_key, step_label in PREPARATION_STEPS:
        row = step_map.get(step_key)
        editor_state.append(
            {
                "step_key": step_key,
                "step_label": step_label,
                "completed": bool(row["completed"]) if row is not None else False,
                "note": normalize_text(row["note"]) if row is not None else "",
            }
        )
    return editor_state


def build_document_sections(documents_df: pd.DataFrame, checkpoints_df: pd.DataFrame, client_id: int) -> list[dict]:
    if documents_df.empty or "client_id" not in documents_df.columns:
        return []

    step_map = {}
    if not checkpoints_df.empty:
        filtered = checkpoints_df[checkpoints_df["client_id"] == client_id]
        step_map = {row["step_key"]: row for _, row in filtered.iterrows()}

    client_docs_df = documents_df[documents_df["client_id"] == client_id].copy()
    if client_docs_df.empty:
        return []

    client_docs_df["categoria_documento"] = client_docs_df.apply(
        lambda row: document_category(row["Tipo Documento"], row["Instituição"]),
        axis=1,
    )

    sections: list[dict] = []
    for section_key, section_label in SECTION_LABELS.items():
        section_docs = client_docs_df[client_docs_df["categoria_documento"] == section_key].copy()
        if section_docs.empty:
            continue
        items = []
        for _, row in section_docs.sort_values(["Tipo Documento", "Instituição"]).iterrows():
            step_key = f"doc_{int(row['document_id'])}"
            stored = step_map.get(step_key)
            items.append(
                {
                    "step_key": step_key,
                    "step_label": normalize_text(row["documento_descricao"]),
                    "completed": bool(stored["completed"]) if stored is not None else False,
                    "note": normalize_text(stored["note"]) if stored is not None else "",
                    "document_status": normalize_text(row["Status"]) or "SEM STATUS",
                    "document_note": normalize_text(row.get("Observação Documento", "")),
                }
            )
        sections.append({"section_key": section_key, "section_label": section_label, "items": items})
    return sections


def load_source(uploaded_file, fallback_path: Path) -> tuple[bytes | None, str]:
    if uploaded_file is not None:
        return uploaded_file.getvalue(), uploaded_file.name
    if fallback_path.exists():
        return fallback_path.read_bytes(), fallback_path.name
    return None, "Arquivo não carregado"


def save_snapshot(snapshot_df: pd.DataFrame) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    if SNAPSHOT_PATH.exists():
        history_df = pd.read_csv(SNAPSHOT_PATH, parse_dates=["data_referencia"])
        history_df = history_df[
            history_df["data_referencia"].dt.date
            != snapshot_df.loc[0, "data_referencia"].date()
        ]
        snapshot_df = pd.concat([history_df, snapshot_df], ignore_index=True)
    snapshot_df.sort_values("data_referencia").to_csv(SNAPSHOT_PATH, index=False)


def load_history() -> pd.DataFrame:
    if not SNAPSHOT_PATH.exists():
        return pd.DataFrame()
    return pd.read_csv(SNAPSHOT_PATH, parse_dates=["data_referencia"]).sort_values("data_referencia")


def save_snapshot_remote(client: Client, snapshot_df: pd.DataFrame) -> None:
    row = snapshot_df.iloc[0]
    payload = {
        "reference_date": row["data_referencia"].date().isoformat(),
        "declaracoes": int(row["declaracoes"]),
        "transmitidas": int(row["transmitidas"]),
        "em_revisao": int(row["em_revisao"]),
        "clientes_com_alguma_documentacao": int(row["clientes_com_alguma_documentacao"]),
        "clientes_docs_completos": int(row["clientes_docs_completos"]),
        "clientes_docs_parciais": int(row["clientes_docs_parciais"]),
        "clientes_sem_documentacao": int(row["clientes_sem_documentacao"]),
        "pct_transmitidas": float(row["pct_transmitidas"]),
        "pct_docs_completos": float(row["pct_docs_completos"]),
    }
    client.table("daily_snapshots").upsert(payload, on_conflict="reference_date").execute()
    invalidate_data_cache()


def load_history_remote(client: Client) -> pd.DataFrame:
    rows = fetch_all_rows(
        client,
        "daily_snapshots",
        "reference_date, declaracoes, transmitidas, em_revisao, clientes_com_alguma_documentacao, clientes_docs_completos, clientes_docs_parciais, clientes_sem_documentacao, pct_transmitidas, pct_docs_completos",
    )
    if not rows:
        return pd.DataFrame()
    history_df = pd.DataFrame(rows)
    history_df["data_referencia"] = pd.to_datetime(history_df["reference_date"], errors="coerce")
    history_df = history_df.drop(columns=["reference_date"])
    return history_df.sort_values("data_referencia")


def ensure_daily_snapshot(snapshot_df: pd.DataFrame, supabase_client: Client | None) -> bool:
    current_time = datetime.now()
    if current_time.hour < 17:
        return False
    snapshot_date = snapshot_df.loc[0, "data_referencia"].date()
    history_df = load_history_remote(supabase_client) if supabase_client is not None else load_history()
    already_saved = (
        not history_df.empty
        and (history_df["data_referencia"].dt.date == snapshot_date).any()
    )
    if already_saved:
        return False
    if supabase_client is not None:
        save_snapshot_remote(supabase_client, snapshot_df)
    else:
        save_snapshot(snapshot_df)
    return True


def build_snapshot(snapshot_date: date, clients_df: pd.DataFrame, people_df: pd.DataFrame) -> pd.DataFrame:
    total_declarations = len(clients_df)
    transmitted = int((clients_df["Status Preenchimento"] == "TRANSMITIDO").sum())
    reviewing = int(clients_df["Status Preenchimento"].str.contains("REVISÃO", na=False).sum())
    docs_any = int((people_df["Documentação"] != "Sem documentação").sum())
    docs_complete = int((people_df["Documentação"] == "Recebido total").sum())
    docs_partial = int((people_df["Documentação"] == "Recebido parcial").sum())
    docs_missing = int((people_df["Documentação"] == "Sem documentação").sum())
    return pd.DataFrame(
        [
            {
                "data_referencia": pd.to_datetime(snapshot_date),
                "declaracoes": total_declarations,
                "transmitidas": transmitted,
                "em_revisao": reviewing,
                "clientes_com_alguma_documentacao": docs_any,
                "clientes_docs_completos": docs_complete,
                "clientes_docs_parciais": docs_partial,
                "clientes_sem_documentacao": docs_missing,
                "pct_transmitidas": safe_percent(transmitted, total_declarations),
                "pct_docs_completos": safe_percent(docs_complete, len(people_df)),
            }
        ]
    )


def display_metric(label: str, value: int, percent: float | None = None) -> None:
    delta = None if percent is None else f"{percent:.1f}%"
    st.metric(label, f"{value}", delta=delta)


def render_login_page() -> None:
    config = load_supabase_public_config()
    if not config:
        st.error("Credenciais do Supabase não encontradas.")
        st.stop()

    left, center, right = st.columns([1, 1.1, 1])
    with center:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), use_container_width=True)
        st.markdown("### IRPF - Controle de Declarações")
        with st.form("supabase_login"):
            email = st.text_input("Email")
            password = st.text_input("Senha", type="password")
            submitted = st.form_submit_button("Entrar", use_container_width=True)
        if submitted:
            try:
                client = create_client(config["url"], config["anon_key"])
                auth_response = client.auth.sign_in_with_password({"email": email, "password": password})
                session = getattr(auth_response, "session", None)
                user = getattr(auth_response, "user", None)
                if session is None:
                    st.error("Não foi possível abrir a sessão.")
                else:
                    st.session_state["supabase_access_token"] = session.access_token
                    st.session_state["supabase_refresh_token"] = session.refresh_token
                    st.session_state["supabase_user_email"] = getattr(user, "email", email)
                    st.rerun()
            except Exception as exc:
                st.error(f"Falha no login: {exc}")


def render_app_header(user_profile: dict[str, object]) -> None:
    logo_col, title_col, action_col = st.columns([1, 5, 1.2], vertical_alignment="center")
    with logo_col:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), use_container_width=True)
    with title_col:
        st.title("IRPF - Controle de Declarações")
    with action_col:
        st.caption(user_profile.get("display_name", "Usuário"))
        if st.button("Sair", use_container_width=True):
            clear_supabase_session()
            st.rerun()


def render_sector_selector(user_profile: dict[str, object]) -> str:
    allowed_sectors = user_profile.get("allowed_sectors", []) or ["Comercial", "Preenchimento", "Revisão"]
    current_value = st.session_state.get("selected_sector", allowed_sectors[0])
    if current_value not in allowed_sectors:
        current_value = allowed_sectors[0]
    selected_sector = st.radio(
        "Setor",
        options=allowed_sectors,
        index=allowed_sectors.index(current_value),
        horizontal=True,
        label_visibility="collapsed",
    )
    st.session_state["selected_sector"] = selected_sector
    return selected_sector


def save_client_record(client: Client, client_payload: dict[str, object], private_payload: dict[str, object], client_id: int | None = None) -> int:
    timestamp = datetime.utcnow().replace(microsecond=0).isoformat()
    client_payload = {**client_payload, "updated_at": timestamp}
    if client_id is None:
        response = client.table("clients").insert(client_payload).execute()
        saved_row = (response.data or [None])[0]
        if not saved_row:
            raise ValueError("Não foi possível criar o cliente.")
        client_id = int(saved_row["id"])
    else:
        client.table("clients").update(client_payload).eq("id", client_id).execute()
    client.table("client_private").upsert(
        {
            "client_id": client_id,
            "cpf": normalize_text(private_payload.get("cpf", "")),
            "phone": normalize_text(private_payload.get("phone", "")),
            "gov_password": normalize_text(private_payload.get("gov_password", "")),
            "has_digital_certificate": bool(private_payload.get("has_digital_certificate", False)),
            "power_of_attorney": normalize_text(private_payload.get("power_of_attorney", "")),
            "updated_at": timestamp,
        },
        on_conflict="client_id",
    ).execute()
    invalidate_data_cache()
    return client_id


def refresh_client_documentation_status(client: Client, client_id: int) -> None:
    docs_response = client.table("documents").select("status").eq("client_id", client_id).execute()
    statuses = [normalize_text(row.get("status", "")).upper() for row in (docs_response.data or [])]
    total = len(statuses)
    received = sum(status == "RECEBIDO" for status in statuses)
    current_client_response = client.table("clients").select("tax_status").eq("id", client_id).limit(1).execute()
    current_client = (current_client_response.data or [{}])[0]
    current_tax_status = normalize_text(current_client.get("tax_status", "")).upper()
    documentation_label = documentation_status(total, received)
    timestamp = datetime.utcnow().replace(microsecond=0).isoformat()
    update_payload = {
        "documentation_status": documentation_label,
        "preparation_queue_status": preparation_queue_status(total, received),
        "updated_at": timestamp,
    }
    auto_managed_statuses = {"", "SEM STATUS", "PENDENTE", "PRONTO PARA PREENCHER"}
    if current_tax_status in auto_managed_statuses:
        update_payload["tax_status"] = "PRONTO PARA PREENCHER" if documentation_label == "Recebido total" else "PENDENTE"
    try:
        client.table("clients").update(update_payload).eq("id", client_id).execute()
    except Exception as exc:
        if "preparation_queue_status" not in str(exc):
            raise
        fallback_payload = {key: value for key, value in update_payload.items() if key != "preparation_queue_status"}
        client.table("clients").update(fallback_payload).eq("id", client_id).execute()


def save_document_record(
    client: Client,
    client_id: int,
    document_type: str,
    institution: str,
    status: str,
    last_update: date | None,
    control_key: str,
    notes: str = "",
) -> None:
    payload = {
        "client_id": client_id,
        "document_type": normalize_text(document_type) or "Não informado",
        "institution": normalize_text(institution) or "Não informada",
        "status": normalize_text(status).upper() or "SEM STATUS",
        "last_update": last_update.isoformat() if last_update else None,
        "control_key": normalize_text(control_key),
        "notes": normalize_text(notes),
    }
    try:
        client.table("documents").insert(payload).execute()
    except Exception as exc:
        if "notes" not in str(exc):
            raise
        payload.pop("notes", None)
        client.table("documents").insert(payload).execute()
    refresh_client_documentation_status(client, client_id)
    invalidate_data_cache()


def update_document_record(
    client: Client,
    document_id: int,
    client_id: int,
    document_type: str,
    institution: str,
    status: str,
    last_update: date | None,
    control_key: str,
    notes: str = "",
) -> None:
    payload = {
        "document_type": normalize_text(document_type) or "Não informado",
        "institution": normalize_text(institution) or "Não informada",
        "status": normalize_text(status).upper() or "SEM STATUS",
        "last_update": last_update.isoformat() if last_update else None,
        "control_key": normalize_text(control_key),
        "notes": normalize_text(notes),
        "updated_at": datetime.utcnow().replace(microsecond=0).isoformat(),
    }
    try:
        client.table("documents").update(payload).eq("id", document_id).execute()
    except Exception as exc:
        if "notes" not in str(exc):
            raise
        payload.pop("notes", None)
        client.table("documents").update(payload).eq("id", document_id).execute()
    refresh_client_documentation_status(client, client_id)
    invalidate_data_cache()


def save_document_bulk_updates(client: Client, document_rows: list[dict], client_id: int) -> None:
    timestamp = datetime.utcnow().replace(microsecond=0).isoformat()
    for row in document_rows:
        payload = {
            "status": normalize_text(row.get("Status", "")).upper() or "SEM STATUS",
            "last_update": row.get("last_update"),
            "updated_at": timestamp,
        }
        if "Observação Documento" in row:
            payload["notes"] = normalize_text(row.get("Observação Documento", ""))
        try:
            client.table("documents").update(payload).eq("id", int(row["document_id"])).execute()
        except Exception as exc:
            if "notes" not in str(exc):
                raise
            payload.pop("notes", None)
            client.table("documents").update(payload).eq("id", int(row["document_id"])).execute()
    refresh_client_documentation_status(client, client_id)
    invalidate_data_cache()


def delete_document_record(client: Client, document_id: int, client_id: int) -> None:
    client.table("documents").delete().eq("id", document_id).execute()
    refresh_client_documentation_status(client, client_id)
    invalidate_data_cache()


def delete_client_record(client: Client, client_id: int) -> None:
    client.table("clients").delete().eq("id", client_id).execute()
    invalidate_data_cache()


def save_batch_client_updates(client: Client, rows: list[dict], acting_as: str) -> None:
    timestamp = datetime.utcnow().replace(microsecond=0).isoformat()
    for row in rows:
        client.table("clients").update(
            {
                "assigned_preparer": normalize_text(row.get("Responsável pelo Preenchimento", "")),
                "tax_status": normalize_text(row.get("Status Preenchimento", "")),
                "updated_at": timestamp,
            }
        ).eq("id", int(row["client_id"])).execute()
    invalidate_data_cache()


def build_standard_template() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "NOME": "CLIENTE EXEMPLO",
                "CPF": "000.000.000-00",
                "Grupo": "Grupo exemplo",
                "Reunião": "Pendente",
                "Nivel de Complexidade": "Médio",
                "Status Preenchimento": "PENDENTE",
                "Responsável pelo Preenchimento": "Não atribuído",
                "Status Pós-Envio": "Não informado",
                "Telefone": "(00) 9 0000-0000",
                "Senha Gov": "",
                "Cadastro de Procuração": "Não informado",
                "Tipo Documento": "Informe de rendimentos",
                "Instituição": "Banco/empresa exemplo",
                "Status Documento": "PENDENTE",
                "Última Atualização": date.today().strftime("%d/%m/%Y"),
                "chave_controle": "",
            }
        ],
        columns=STANDARD_IMPORT_COLUMNS,
    )


def parse_standard_import(file_bytes: bytes, file_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw_df = read_table_file(file_bytes, file_name)
    selected_df = select_columns(raw_df, STANDARD_IMPORT_COLUMNS)
    client_source = selected_df.rename(columns={"Status Documento": "Status"})
    clients_df = parse_clients(client_source[CLIENT_COLUMNS].to_csv(index=False).encode("utf-8"), "clientes.csv")

    docs_source = pd.DataFrame(
        {
            "Nome Pessoa": selected_df["NOME"],
            "Tipo Documento": selected_df["Tipo Documento"],
            "Instituição": selected_df["Instituição"],
            "Status": selected_df["Status Documento"],
            "Última Atualização": selected_df["Última Atualização"],
            "chave_controle": selected_df["chave_controle"],
        }
    )
    docs_source = docs_source[docs_source["Tipo Documento"].map(normalize_text) != ""].copy()
    documents_df = parse_documents(docs_source.to_csv(index=False).encode("utf-8"), "documentos.csv")
    return clients_df.drop_duplicates("chave_pessoa"), documents_df


def document_status_priority(value: object) -> int:
    status = normalize_key(value)
    if status == "RECEBIDO":
        return 2
    if status in {"PENDENTE", "SOLICITAR DOCUMENTO"}:
        return 1
    return 0


def deduplicate_imported_documents(documents_df: pd.DataFrame) -> pd.DataFrame:
    if documents_df.empty:
        return documents_df
    deduped_df = documents_df.copy()
    deduped_df["_doc_key"] = deduped_df.apply(
        lambda row: (
            normalize_text(row.get("chave_pessoa", "")),
            normalize_key(row.get("Tipo Documento", "")),
            normalize_key(row.get("Instituição", "")),
        ),
        axis=1,
    )
    deduped_df["_doc_key_sort"] = deduped_df["_doc_key"].map(lambda key: "|".join(key))
    deduped_df["_status_priority"] = deduped_df["Status"].map(document_status_priority)
    deduped_df["_last_update_sort"] = pd.to_datetime(
        deduped_df["Última Atualização"],
        errors="coerce",
        dayfirst=True,
    ).fillna(pd.Timestamp("1900-01-01"))
    deduped_df = deduped_df.sort_values(
        ["_doc_key_sort", "_status_priority", "_last_update_sort"],
        kind="stable",
    )
    deduped_df = deduped_df.drop_duplicates("_doc_key", keep="last")
    return deduped_df.drop(
        columns=["_doc_key", "_doc_key_sort", "_status_priority", "_last_update_sort"]
    ).reset_index(drop=True)


def build_import_comparison(
    imported_clients_df: pd.DataFrame,
    imported_documents_df: pd.DataFrame,
    people_df: pd.DataFrame,
    documents_df: pd.DataFrame,
    selected_client_fields: set[str] | None = None,
    selected_document_fields: set[str] | None = None,
) -> dict[str, pd.DataFrame]:
    imported_documents_df = deduplicate_imported_documents(imported_documents_df)
    selected_client_fields = set(CLIENT_IMPORT_UPDATE_FIELDS) if selected_client_fields is None else set(selected_client_fields)
    selected_document_fields = set(DOCUMENT_IMPORT_UPDATE_FIELDS) if selected_document_fields is None else set(selected_document_fields)
    current_people = people_df.set_index("chave_pessoa", drop=False) if "chave_pessoa" in people_df.columns else pd.DataFrame()
    current_docs = documents_df.copy()
    current_docs_by_key = {}
    if not current_docs.empty:
        current_docs["doc_key"] = current_docs.apply(
            lambda row: (
                normalize_text(row["chave_pessoa"]),
                normalize_key(row["Tipo Documento"]),
                normalize_key(row["Instituição"]),
            ),
            axis=1,
        )
        current_docs_by_key = {row["doc_key"]: row for _, row in current_docs.iterrows()}

    new_clients = []
    changed_clients = []
    compare_columns = [
        ("Grupo", "Grupo"),
        ("Reunião", "Reunião"),
        ("Nivel de Complexidade", "Nivel de Complexidade"),
        ("Status Preenchimento", "Status Preenchimento"),
        ("Responsável pelo Preenchimento", "Responsável pelo Preenchimento"),
        ("Status Pós-Envio", "Status Pós-Envio"),
        ("CPF", "CPF"),
        ("Telefone", "Telefone"),
        ("Senha Gov", "Senha Gov"),
        ("Cadastro de Procuração", "Cadastro de Procuração"),
    ]
    for _, row in imported_clients_df.iterrows():
        key = row["chave_pessoa"]
        if current_people.empty or key not in current_people.index:
            new_clients.append({"NOME": row["NOME"], "Grupo": row["Grupo"], "Status": "Novo cliente"})
            continue
        current_row = current_people.loc[key]
        differences = []
        for source_column, current_column in compare_columns:
            if source_column not in selected_client_fields:
                continue
            new_value = normalize_text(row.get(source_column, ""))
            old_value = normalize_text(current_row.get(current_column, ""))
            if new_value and new_value != old_value:
                differences.append(f"{current_column}: {old_value or '-'} -> {new_value}")
        if differences:
            changed_clients.append({"NOME": row["NOME"], "Alterações": "\n".join(differences)})

    new_documents = []
    changed_documents = []
    for _, row in imported_documents_df.iterrows():
        doc_key = (normalize_text(row["chave_pessoa"]), normalize_key(row["Tipo Documento"]), normalize_key(row["Instituição"]))
        if not current_docs_by_key or doc_key not in current_docs_by_key:
            new_documents.append(
                {
                    "NOME": row["Nome Pessoa"],
                    "Documento": row["documento_descricao"],
                    "Status": row["Status"],
                }
            )
            continue
        current_doc = current_docs_by_key[doc_key]
        differences = []
        if "Status Documento" in selected_document_fields:
            new_status = normalize_text(row["Status"]).upper()
            old_status = normalize_text(current_doc.get("Status", "")).upper()
            if new_status and new_status != old_status:
                differences.append(f"Status: {old_status or '-'} -> {new_status}")
        if "Última Atualização" in selected_document_fields:
            new_date = parse_optional_date(row["Última Atualização"])
            old_date = parse_optional_date(current_doc.get("Última Atualização"))
            if new_date is not None and new_date != old_date:
                old_date_label = old_date.strftime("%d/%m/%Y") if old_date else "-"
                differences.append(f"Última atualização: {old_date_label} -> {new_date.strftime('%d/%m/%Y')}")
        if "chave_controle" in selected_document_fields:
            new_control_key = normalize_text(row.get("chave_controle", ""))
            old_control_key = normalize_text(current_doc.get("chave_controle", ""))
            if new_control_key and new_control_key != old_control_key:
                differences.append(f"Chave de controle: {old_control_key or '-'} -> {new_control_key}")
        if differences:
            changed_documents.append(
                {
                    "NOME": row["Nome Pessoa"],
                    "Documento": row["documento_descricao"],
                    "Alteração": "\n".join(differences),
                }
            )

    return {
        "new_clients": pd.DataFrame(new_clients),
        "changed_clients": pd.DataFrame(changed_clients),
        "new_documents": pd.DataFrame(new_documents),
        "changed_documents": pd.DataFrame(changed_documents),
    }


def import_value_or_existing(new_value: object, existing_value: object = "", placeholders: set[str] | None = None) -> str:
    text = normalize_text(new_value)
    placeholder_keys = placeholders or set()
    if not text or normalize_key(text) in placeholder_keys:
        return normalize_text(existing_value)
    return text


def parse_optional_date(value: object) -> date | None:
    parsed = pd.to_datetime(value, errors="coerce", dayfirst=True)
    return None if pd.isna(parsed) else parsed.date()


def apply_import_updates(
    client: Client,
    imported_clients_df: pd.DataFrame,
    imported_documents_df: pd.DataFrame,
    people_df: pd.DataFrame,
    documents_df: pd.DataFrame,
    selected_client_fields: set[str] | None = None,
    selected_document_fields: set[str] | None = None,
) -> tuple[int, int]:
    imported_documents_df = deduplicate_imported_documents(imported_documents_df)
    selected_client_fields = selected_client_fields or set()
    selected_document_fields = selected_document_fields or set()
    current_people = people_df.set_index("chave_pessoa", drop=False) if "chave_pessoa" in people_df.columns else pd.DataFrame()
    client_ids: dict[str, int] = {}
    updated_clients = 0

    for _, row in imported_clients_df.iterrows():
        key = row["chave_pessoa"]
        existing_id = None
        current_row = pd.Series(dtype=object)
        if not current_people.empty and key in current_people.index:
            current_row = current_people.loc[key]
            existing_id = int(current_row["client_id"])
        generic_placeholders = {
            "SEM GRUPO",
            "SEM REUNIAO INFORMADA",
            "NAO INFORMADO",
            "NAO ATRIBUIDO",
            "SEM STATUS",
        }
        imported_gov_password = normalize_text(row["Senha Gov"])
        imported_has_certificate = bool(row.get("Tem Certificado Digital", False))
        existing_has_certificate = bool(current_row.get("Tem Certificado Digital", False)) if existing_id else False
        has_digital_certificate = (
            imported_has_certificate
            if imported_has_certificate or imported_gov_password
            else existing_has_certificate
        )

        def client_field_value(field_name: str, imported_value: object, current_value: object = "", placeholders: set[str] | None = None) -> str:
            if existing_id is not None and field_name not in selected_client_fields:
                return normalize_text(current_value)
            return import_value_or_existing(imported_value, current_value, placeholders)

        def private_field_value(field_name: str, imported_value: object, current_value: object = "", placeholders: set[str] | None = None) -> str:
            if existing_id is not None and field_name not in selected_client_fields:
                return normalize_text(current_value)
            return import_value_or_existing(imported_value, current_value, placeholders)

        if existing_id is not None and "Senha Gov" not in selected_client_fields:
            has_digital_certificate = existing_has_certificate

        saved_id = save_client_record(
            client,
            {
                "normalized_name": key,
                "full_name": normalize_text(row["NOME"]) if existing_id is None else normalize_text(current_row.get("NOME", row["NOME"])),
                "group_name": client_field_value("Grupo", row["Grupo"], current_row.get("Grupo", ""), generic_placeholders),
                "meeting_status": client_field_value("Reunião", row["Reunião"], current_row.get("Reunião", ""), generic_placeholders),
                "complexity_level": client_field_value(
                    "Nivel de Complexidade",
                    row["Nivel de Complexidade"],
                    current_row.get("Nivel de Complexidade", ""),
                    generic_placeholders,
                ),
                "tax_status": client_field_value(
                    "Status Preenchimento",
                    row["Status Preenchimento"],
                    current_row.get("Status Preenchimento", ""),
                    {"SEM STATUS"},
                ),
                "assigned_preparer": client_field_value(
                    "Responsável pelo Preenchimento",
                    row["Responsável pelo Preenchimento"],
                    current_row.get("Responsável pelo Preenchimento", ""),
                    {"NAO ATRIBUIDO"},
                ),
                "post_filing_status": client_field_value(
                    "Status Pós-Envio",
                    row["Status Pós-Envio"],
                    current_row.get("Status Pós-Envio", ""),
                    generic_placeholders,
                ),
                "documentation_status": normalize_text(current_row.get("Documentação", "")) or "Sem documentação",
                "active": True,
            },
            {
                "cpf": private_field_value("CPF", normalize_cpf(row["CPF"]), current_row.get("CPF", "")),
                "phone": private_field_value("Telefone", normalize_phone(row["Telefone"]), current_row.get("Telefone", "")),
                "gov_password": private_field_value("Senha Gov", imported_gov_password, current_row.get("Senha Gov", "")),
                "has_digital_certificate": has_digital_certificate,
                "power_of_attorney": private_field_value(
                    "Cadastro de Procuração",
                    row["Cadastro de Procuração"],
                    current_row.get("Cadastro de Procuração", ""),
                    {"NAO INFORMADO"},
                ),
            },
            client_id=existing_id,
        )
        client_ids[key] = saved_id
        updated_clients += 1

    current_docs = documents_df.copy()
    current_docs_by_key = {}
    if not current_docs.empty:
        current_docs["doc_key"] = current_docs.apply(
            lambda row: (
                int(row["client_id"]),
                normalize_key(row["Tipo Documento"]),
                normalize_key(row["Instituição"]),
            ),
            axis=1,
        )
        current_docs_by_key = {row["doc_key"]: row for _, row in current_docs.iterrows()}

    updated_documents = 0
    processed_doc_keys: set[tuple[int, str, str]] = set()
    for _, row in imported_documents_df.iterrows():
        key = row["chave_pessoa"]
        if key not in client_ids:
            existing_id = None
            if not current_people.empty and key in current_people.index:
                existing_id = int(current_people.loc[key]["client_id"])
            else:
                existing_id = save_client_record(
                    client,
                    {
                        "normalized_name": key,
                        "full_name": normalize_text(row["Nome Pessoa"]),
                        "group_name": "",
                        "meeting_status": "",
                        "complexity_level": "",
                        "tax_status": "PENDENTE",
                        "assigned_preparer": "Não atribuído",
                        "post_filing_status": "",
                        "documentation_status": "",
                        "active": True,
                    },
                    {"cpf": "", "phone": "", "gov_password": "", "has_digital_certificate": False, "power_of_attorney": ""},
                    client_id=None,
                )
            client_ids[key] = existing_id
        client_id = client_ids[key]
        doc_key = (client_id, normalize_key(row["Tipo Documento"]), normalize_key(row["Instituição"]))
        if doc_key in processed_doc_keys:
            continue
        processed_doc_keys.add(doc_key)
        last_update_value = parse_optional_date(row["Última Atualização"])
        if current_docs_by_key and doc_key in current_docs_by_key:
            current_doc = current_docs_by_key[doc_key]
            existing_last_update = parse_optional_date(current_doc.get("Última Atualização"))
            next_last_update = (
                last_update_value
                if "Última Atualização" in selected_document_fields and last_update_value is not None
                else existing_last_update
            )
            update_document_record(
                client,
                document_id=int(current_doc["document_id"]),
                client_id=client_id,
                document_type=current_doc.get("Tipo Documento", row["Tipo Documento"]),
                institution=current_doc.get("Instituição", row["Instituição"]),
                status=(
                    import_value_or_existing(row["Status"], current_doc.get("Status", ""), {"SEM STATUS"})
                    if "Status Documento" in selected_document_fields
                    else normalize_text(current_doc.get("Status", ""))
                ),
                last_update=next_last_update,
                control_key=(
                    import_value_or_existing(row["chave_controle"], current_doc.get("chave_controle", ""))
                    if "chave_controle" in selected_document_fields
                    else normalize_text(current_doc.get("chave_controle", ""))
                ),
            )
        else:
            save_document_record(
                client,
                client_id=client_id,
                document_type=row["Tipo Documento"],
                institution=row["Instituição"],
                status=row["Status"],
                last_update=last_update_value,
                control_key=row["chave_controle"],
            )
        updated_documents += 1

    return updated_clients, updated_documents


def render_commercial_page(
    people_df: pd.DataFrame,
    supabase_client: Client | None,
    documents_df: pd.DataFrame,
    team_df: pd.DataFrame,
    user_profile: dict[str, object],
) -> None:
    render_commercial_sector(
        build_sector_context(),
        people_df,
        supabase_client,
        documents_df,
        team_df,
        user_profile,
    )


def render_registry_page(
    supabase_client: Client | None,
    people_df: pd.DataFrame,
    documents_df: pd.DataFrame,
    team_df: pd.DataFrame,
    user_profile: dict[str, object],
    show_header: bool = True,
) -> None:
    render_registry_sector(
        build_sector_context(),
        supabase_client,
        people_df,
        documents_df,
        team_df,
        user_profile,
        show_header,
    )


def save_preparation_updates(
    client: Client,
    client_id: int,
    assigned_preparer: str,
    tax_status: str,
    acting_as: str,
    steps_payload: list[dict],
    allow_checkpoint_updates: bool = True,
) -> None:
    timestamp = datetime.utcnow().replace(microsecond=0).isoformat()
    client.table("clients").update(
        {
            "assigned_preparer": assigned_preparer,
            "tax_status": tax_status,
            "updated_at": timestamp,
        }
    ).eq("id", client_id).execute()
    save_stage_checkpoint_if_missing(client, client_id, tax_status, acting_as, timestamp)
    if allow_checkpoint_updates and steps_payload:
        payload = [
            {
                "client_id": client_id,
                "step_key": item["step_key"],
                "step_label": item["step_label"],
                "completed": item["completed"],
                "note": item["note"],
                "updated_by": acting_as,
                "updated_at": timestamp,
            }
            for item in steps_payload
        ]
        client.table("declaration_checkpoints").upsert(
            payload,
            on_conflict="client_id,step_key",
        ).execute()
    invalidate_data_cache()


def build_sector_context() -> dict[str, object]:
    return {
        "st": st,
        "pd": pd,
        "date": date,
        "STATUS_OPTIONS": STATUS_OPTIONS,
        "DOCUMENT_TYPE_OPTIONS": DOCUMENT_TYPE_OPTIONS,
        "DOCUMENT_STATUS_OPTIONS": DOCUMENT_STATUS_OPTIONS,
        "AVAILABLE_DECLARATION_STATUSES": AVAILABLE_DECLARATION_STATUSES,
        "PREPARATION_STEPS": PREPARATION_STEPS,
        "normalize_text": normalize_text,
        "normalize_key": normalize_key,
        "normalize_cpf": normalize_cpf,
        "normalize_phone": normalize_phone,
        "is_unassigned_preparer": is_unassigned_preparer,
        "build_available_preparation_queue": build_available_preparation_queue,
        "status_progress_percent": status_progress_percent,
        "save_client_record": save_client_record,
        "save_document_record": save_document_record,
        "update_document_record": update_document_record,
        "delete_document_record": delete_document_record,
        "delete_client_record": delete_client_record,
        "save_document_bulk_updates": save_document_bulk_updates,
        "build_checkpoint_editor_state": build_checkpoint_editor_state,
        "build_document_sections": build_document_sections,
        "save_batch_client_updates": save_batch_client_updates,
        "save_preparation_updates": save_preparation_updates,
        "load_history_remote": load_history_remote,
        "load_history": load_history,
        "save_snapshot_remote": save_snapshot_remote,
        "save_snapshot": save_snapshot,
    }


def render_preparation_editor(
    supabase_client: Client | None,
    people_df: pd.DataFrame,
    documents_df: pd.DataFrame,
    checkpoints_df: pd.DataFrame,
    team_df: pd.DataFrame,
    user_profile: dict[str, object],
) -> None:
    render_preparation_sector(
        build_sector_context(),
        supabase_client,
        people_df,
        documents_df,
        checkpoints_df,
        team_df,
        user_profile,
    )


def render_review_page(
    people_df: pd.DataFrame,
    snapshot_df: pd.DataFrame,
    supabase_client: Client | None,
    checkpoints_df: pd.DataFrame,
    documents_df: pd.DataFrame,
    user_profile: dict[str, object],
) -> None:
    render_review_sector(build_sector_context(), people_df, snapshot_df, supabase_client, checkpoints_df, documents_df, user_profile)


def save_stage_checkpoint_if_missing(client: Client, client_id: int, tax_status: str, acting_as: str, timestamp: str) -> None:
    stage_config = STAGE_CHECKPOINTS.get(canonical_status(tax_status))
    if not stage_config:
        return
    existing_response = (
        client.table("declaration_checkpoints")
        .select("id")
        .eq("client_id", client_id)
        .eq("step_key", stage_config["step_key"])
        .limit(1)
        .execute()
    )
    if existing_response.data:
        return
    client.table("declaration_checkpoints").insert(
        {
            "client_id": client_id,
            "step_key": stage_config["step_key"],
            "step_label": stage_config["step_label"],
            "completed": True,
            "note": "",
            "updated_by": acting_as,
            "updated_at": timestamp,
        }
    ).execute()


def prepare_export_sheet(df: pd.DataFrame) -> pd.DataFrame:
    export_df = df.copy()

    def format_export_value(value: object) -> object:
        if value is None:
            return ""
        try:
            if pd.isna(value):
                return ""
        except (TypeError, ValueError):
            pass
        if isinstance(value, pd.Timestamp):
            if value.tzinfo is not None:
                value = value.tz_convert(None)
            return value.strftime("%d/%m/%Y %H:%M")
        if isinstance(value, datetime):
            if value.tzinfo is not None:
                value = value.replace(tzinfo=None)
            return value.strftime("%d/%m/%Y %H:%M")
        if isinstance(value, date):
            return value.strftime("%d/%m/%Y")
        return value

    for column in export_df.columns:
        if pd.api.types.is_datetime64_any_dtype(export_df[column]):
            export_df[column] = export_df[column].map(format_export_value)
        elif export_df[column].dtype == "object":
            export_df[column] = export_df[column].map(format_export_value)
    return export_df


def build_full_database_export(people_df: pd.DataFrame, documents_df: pd.DataFrame, checkpoints_df: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    documents_export_df = documents_df.copy()
    if not documents_export_df.empty:
        documents_export_df = documents_export_df.merge(
            people_df[["client_id", "NOME", "Grupo", "Responsável pelo Preenchimento", "Status Preenchimento"]],
            on="client_id",
            how="left",
            suffixes=("", "_cliente"),
        )
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        prepare_export_sheet(people_df).to_excel(writer, sheet_name="Clientes", index=False)
        prepare_export_sheet(documents_export_df).to_excel(writer, sheet_name="Documentos", index=False)
        prepare_export_sheet(checkpoints_df).to_excel(writer, sheet_name="Checkpoints", index=False)
    return output.getvalue()


def render_import_page(
    supabase_client: Client | None,
    people_df: pd.DataFrame,
    documents_df: pd.DataFrame,
    checkpoints_df: pd.DataFrame,
    user_profile: dict[str, object],
) -> None:
    st.header("Cadastros")
    allowed_import_emails = {"paulo.nunes@gestaocontabil.com", "heverton@gestaocontabil.com"}
    user_email = normalize_text(user_profile.get("email", "")).lower()
    if user_email not in allowed_import_emails:
        st.warning("Esta área é restrita ao Paulo e ao Heverton.")
        return
    if supabase_client is None:
        st.info("Faça login para importar dados para o banco.")
        return

    st.markdown("**Importação e conferência do banco**")
    st.download_button(
        "Exportar banco completo em XLSX",
        data=build_full_database_export(people_df, documents_df, checkpoints_df),
        file_name=f"irpf_banco_completo_{date.today().isoformat()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    template_df = build_standard_template()
    st.download_button(
        "Baixar planilha padrão",
        data=template_df.to_csv(index=False, sep=";").encode("utf-8-sig"),
        file_name="modelo_importacao_irpf.csv",
        mime="text/csv",
        use_container_width=True,
    )

    upload_col_1, upload_col_2, upload_col_3 = st.columns(3)
    with upload_col_1:
        standard_upload = st.file_uploader(
            "Planilha padrão",
            type=["csv", "xlsx", "xls"],
            key="standard_import_upload",
        )
    with upload_col_2:
        clients_upload = st.file_uploader(
            "Planilha de clientes",
            type=["csv", "xlsx", "xls"],
            key="clients_import_upload",
        )
    with upload_col_3:
        documents_upload = st.file_uploader(
            "Planilha de documentos",
            type=["csv", "xlsx", "xls"],
            key="documents_import_upload",
        )

    if standard_upload is None and clients_upload is None and documents_upload is None:
        st.info("Envie a planilha padrão ou uma das planilhas atuais para comparar com o banco.")
        return

    try:
        if standard_upload is not None:
            imported_clients_df, imported_documents_df = parse_standard_import(
                standard_upload.getvalue(),
                standard_upload.name,
            )
        else:
            if clients_upload is not None:
                imported_clients_df = parse_clients(clients_upload.getvalue(), clients_upload.name)
            else:
                imported_clients_df = pd.DataFrame(
                    columns=CLIENT_COLUMNS + ["Documentação Informada", "Tem Certificado Digital", "chave_pessoa"]
                )
            if documents_upload is not None:
                imported_documents_df = parse_documents(documents_upload.getvalue(), documents_upload.name)
            else:
                imported_documents_df = pd.DataFrame(columns=DOCUMENT_COLUMNS + ["documento_descricao", "chave_pessoa"])
    except Exception as exc:
        st.error(f"Não foi possível ler a importação: {exc}")
        return

    imported_clients_df = imported_clients_df[
        imported_clients_df["chave_pessoa"].map(lambda value: normalize_text(value) not in ["", "SEM NOME IDENTIFICADO"])
    ].copy()
    imported_documents_df = imported_documents_df[
        imported_documents_df["chave_pessoa"].map(lambda value: normalize_text(value) not in ["", "SEM NOME IDENTIFICADO"])
    ].copy()

    field_col_1, field_col_2 = st.columns(2)
    with field_col_1:
        selected_client_fields = set(
            st.multiselect(
                "Campos de clientes que serão atualizados",
                options=CLIENT_IMPORT_UPDATE_FIELDS,
                default=[],
                key="import_client_update_fields",
            )
        )
    with field_col_2:
        selected_document_fields = set(
            st.multiselect(
                "Campos de documentos que serão atualizados",
                options=DOCUMENT_IMPORT_UPDATE_FIELDS,
                default=["Status Documento", "Última Atualização"],
                key="import_document_update_fields",
            )
        )

    comparison = build_import_comparison(
        imported_clients_df,
        imported_documents_df,
        people_df,
        documents_df,
        selected_client_fields,
        selected_document_fields,
    )
    metric_1, metric_2, metric_3, metric_4 = st.columns(4)
    with metric_1:
        st.metric("Novos clientes", len(comparison["new_clients"]))
    with metric_2:
        st.metric("Clientes com alteração", len(comparison["changed_clients"]))
    with metric_3:
        st.metric("Novos documentos", len(comparison["new_documents"]))
    with metric_4:
        st.metric("Documentos alterados", len(comparison["changed_documents"]))

    diff_tabs = st.tabs(["Novos clientes", "Clientes alterados", "Novos documentos", "Documentos alterados"])
    with diff_tabs[0]:
        if comparison["new_clients"].empty:
            st.caption("Nenhum cliente novo encontrado.")
        else:
            st.dataframe(comparison["new_clients"], use_container_width=True, hide_index=True)
    with diff_tabs[1]:
        if comparison["changed_clients"].empty:
            st.caption("Nenhuma alteração cadastral encontrada.")
        else:
            st.dataframe(comparison["changed_clients"], use_container_width=True, hide_index=True)
    with diff_tabs[2]:
        if comparison["new_documents"].empty:
            st.caption("Nenhum documento novo encontrado.")
        else:
            st.dataframe(comparison["new_documents"], use_container_width=True, hide_index=True)
    with diff_tabs[3]:
        if comparison["changed_documents"].empty:
            st.caption("Nenhuma alteração de documento encontrada.")
        else:
            st.dataframe(comparison["changed_documents"], use_container_width=True, hide_index=True)

    total_changes = sum(len(df) for df in comparison.values())
    confirm_import = st.checkbox("Conferi as diferenças e quero atualizar o banco")
    if st.button(
        "Aplicar atualização no banco",
        use_container_width=True,
        disabled=not confirm_import or total_changes == 0,
    ):
        try:
            updated_clients, updated_documents = apply_import_updates(
                supabase_client,
                imported_clients_df,
                imported_documents_df,
                people_df,
                documents_df,
                selected_client_fields,
                selected_document_fields,
            )
            st.success(
                f"Importação aplicada. Clientes processados: {updated_clients}. Documentos processados: {updated_documents}."
            )
            st.rerun()
        except Exception as exc:
            st.error(f"Não foi possível aplicar a importação: {exc}")


def main() -> None:
    st.set_page_config(page_title="IRPF - Controle de Declarações", layout="wide")

    supabase_client = build_supabase_client()
    if supabase_client is None or not st.session_state.get("supabase_user_email"):
        render_login_page()
        st.stop()

    try:
        bundle = load_supabase_bundle_cached(supabase_client)
        clients_df = bundle["clients_df"]
        documents_df = bundle["documents_df"]
        private_df = bundle["private_df"]
        team_df = bundle["team_df"]
        checkpoints_df = bundle["checkpoints_df"]
        user_profile = get_user_profile(team_df, st.session_state.get("supabase_user_email", ""), "Supabase")
    except Exception as exc:
        st.error(f"Não foi possível carregar o banco de dados: {exc}")
        st.stop()

    if not user_profile.get("allowed_sectors"):
        st.error("Seu usuário está autenticado, mas ainda não foi liberado para nenhum setor.")
        st.stop()

    render_app_header(user_profile)
    selected_sector = render_sector_selector(user_profile)

    people_df = build_people_summary(clients_df, documents_df)
    people_df = attach_private_data(people_df, private_df)
    people_df = attach_progress(people_df, build_checkpoint_summary(checkpoints_df, documents_df))
    snapshot_df = build_snapshot(date.today(), clients_df, people_df)
    auto_snapshot_saved = ensure_daily_snapshot(snapshot_df, supabase_client)

    if auto_snapshot_saved:
        st.success("Posição do dia salva automaticamente após as 17h.")

    if selected_sector == "Comercial":
        render_commercial_page(
            people_df,
            supabase_client,
            documents_df,
            team_df,
            user_profile,
        )
    elif selected_sector == "Preenchimento":
        render_preparation_editor(
            supabase_client,
            people_df,
            documents_df,
            checkpoints_df,
            team_df,
            user_profile,
        )
    elif selected_sector == "Revisão":
        render_review_page(people_df, snapshot_df, supabase_client, checkpoints_df, documents_df, user_profile)
    else:
        render_import_page(
            supabase_client,
            people_df,
            documents_df,
            checkpoints_df,
            user_profile,
        )


if __name__ == "__main__":
    main()
