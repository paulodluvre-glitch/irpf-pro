from __future__ import annotations

from typing import Any


POST_FILING_NOTE_STEP_KEY = "pos_envio_observacoes"


def _with_post_filing_notes(ctx: dict[str, Any], people_df, checkpoints_df):
    pd = ctx["pd"]
    normalize_text = ctx["normalize_text"]

    base_df = people_df.copy()
    if "client_id" not in base_df.columns:
        base_df["client_id"] = None

    notes_df = checkpoints_df.copy()
    if notes_df.empty or "step_key" not in notes_df.columns:
        base_df["Observação Pós-Envio"] = ""
        base_df["Atualização Pós-Envio"] = ""
        return base_df

    notes_df = notes_df[notes_df["step_key"] == POST_FILING_NOTE_STEP_KEY].copy()
    if notes_df.empty:
        base_df["Observação Pós-Envio"] = ""
        base_df["Atualização Pós-Envio"] = ""
        return base_df

    notes_df["updated_at"] = pd.to_datetime(notes_df["updated_at"], errors="coerce")
    notes_df = (
        notes_df.sort_values(["client_id", "updated_at"])
        .drop_duplicates(subset=["client_id"], keep="last")[["client_id", "note", "updated_at"]]
        .rename(columns={"note": "Observação Pós-Envio", "updated_at": "Atualização Pós-Envio"})
    )
    notes_df["Observação Pós-Envio"] = notes_df["Observação Pós-Envio"].fillna("").map(normalize_text)
    return base_df.merge(notes_df, on="client_id", how="left")


def _apply_filters(ctx: dict[str, Any], source_df, status_options: list[str]):
    st = ctx["st"]
    normalize_text = ctx["normalize_text"]

    filter_cols = st.columns([1.2, 1.2, 1.6])
    with filter_cols[0]:
        selected_statuses = st.multiselect(
            "Status pós-envio",
            options=status_options,
            default=status_options,
        )
    with filter_cols[1]:
        group_options = sorted(
            [group for group in source_df["Grupo"].dropna().map(normalize_text).unique().tolist() if group]
        )
        selected_groups = st.multiselect("Grupo", options=group_options)
    with filter_cols[2]:
        name_filter = st.text_input("Buscar por nome", placeholder="Digite parte do nome do cliente")

    filtered_df = source_df.copy()
    if selected_statuses:
        filtered_df = filtered_df[filtered_df["Status Pós-Envio"].isin(selected_statuses)]
    if selected_groups:
        filtered_df = filtered_df[filtered_df["Grupo"].isin(selected_groups)]
    if normalize_text(name_filter):
        needle = normalize_text(name_filter).lower()
        filtered_df = filtered_df[filtered_df["NOME"].map(lambda value: needle in normalize_text(value).lower())]
    return filtered_df


def _render_metrics(ctx: dict[str, Any], source_df, status_options: list[str]) -> None:
    st = ctx["st"]
    counts = source_df["Status Pós-Envio"].value_counts()
    columns = st.columns(len(status_options))
    for column, status in zip(columns, status_options):
        with column:
            st.metric(status, int(counts.get(status, 0)))


def _render_detail_table(ctx: dict[str, Any], filtered_df) -> None:
    st = ctx["st"]
    pd = ctx["pd"]

    table_columns = [
        "NOME",
        "Grupo",
        "Status Pós-Envio",
        "Observação Pós-Envio",
        "Status Preenchimento",
        "Responsável pelo Preenchimento",
        "Documentação",
        "Recebidos / Total",
        "Atualização Pós-Envio",
    ]
    available_columns = [column for column in table_columns if column in filtered_df.columns]
    display_df = filtered_df[available_columns].copy()
    if "Atualização Pós-Envio" in display_df.columns:
        display_df["Atualização Pós-Envio"] = pd.to_datetime(
            display_df["Atualização Pós-Envio"], errors="coerce"
        ).dt.strftime("%d/%m/%Y %H:%M")
        display_df["Atualização Pós-Envio"] = display_df["Atualização Pós-Envio"].fillna("")

    st.dataframe(
        display_df.sort_values(["Status Pós-Envio", "Grupo", "NOME"]),
        use_container_width=True,
        hide_index=True,
    )


def _render_editor(ctx: dict[str, Any], source_df, supabase_client, user_profile: dict[str, object]) -> None:
    st = ctx["st"]
    normalize_text = ctx["normalize_text"]
    canonical_post_filing_status = ctx["canonical_post_filing_status"]
    status_options = ctx["POST_FILING_STATUS_OPTIONS"]
    save_post_filing_update = ctx["save_post_filing_update"]

    st.subheader("Editar cliente")
    if supabase_client is None:
        st.info("Conecte o Supabase para salvar alterações.")
        return

    editable_df = source_df.dropna(subset=["client_id"]).copy()
    if editable_df.empty:
        st.caption("Nenhum cliente disponível para edição.")
        return

    editable_df["client_id"] = editable_df["client_id"].astype(int)
    editable_df = editable_df.sort_values(["NOME", "Grupo"])
    client_lookup = {
        int(row["client_id"]): row
        for _, row in editable_df.drop_duplicates(subset=["client_id"], keep="first").iterrows()
    }
    client_ids = list(client_lookup.keys())

    selected_client_id = st.selectbox(
        "Cliente",
        options=client_ids,
        format_func=lambda client_id: (
            f"{normalize_text(client_lookup[client_id]['NOME'])} | {normalize_text(client_lookup[client_id]['Grupo'])}"
        ),
    )
    selected_row = client_lookup[selected_client_id]
    current_status = canonical_post_filing_status(selected_row.get("Status Pós-Envio", ""))
    current_observation = normalize_text(selected_row.get("Observação Pós-Envio", ""))

    with st.form(f"post_filing_form_{selected_client_id}"):
        status = st.selectbox(
            "Status na Receita Federal",
            options=status_options,
            index=status_options.index(current_status) if current_status in status_options else status_options.index("STATUS A VERIFICAR"),
        )
        observation = st.text_area(
            "Observações",
            value=current_observation,
            height=120,
            placeholder="Ex.: aguardando processamento no e-CAC, pendência conferida, retorno do cliente...",
        )
        submitted = st.form_submit_button("Salvar pós-envio", use_container_width=True)

    if submitted:
        try:
            save_post_filing_update(
                supabase_client,
                selected_client_id,
                status,
                observation,
                normalize_text(user_profile.get("display_name", "")) or "Sistema",
            )
            st.toast("Salvo!")
            st.success("Status de pós-envio atualizado.")
            st.rerun()
        except Exception as exc:
            st.error(f"Não foi possível salvar o pós-envio: {exc}")


def render_post_filing_page(
    ctx: dict[str, Any],
    people_df,
    supabase_client,
    checkpoints_df,
    user_profile: dict[str, object],
) -> None:
    st = ctx["st"]
    canonical_post_filing_status = ctx["canonical_post_filing_status"]
    status_options = ctx["POST_FILING_STATUS_OPTIONS"]

    st.header("Pós-envio")
    source_df = _with_post_filing_notes(ctx, people_df, checkpoints_df)
    source_df["Status Pós-Envio"] = source_df["Status Pós-Envio"].map(canonical_post_filing_status)
    source_df["Observação Pós-Envio"] = source_df["Observação Pós-Envio"].fillna("")

    _render_metrics(ctx, source_df, status_options)
    st.divider()

    st.subheader("Tabela detalhada")
    filtered_df = _apply_filters(ctx, source_df, status_options)
    _render_detail_table(ctx, filtered_df)

    st.divider()
    _render_editor(ctx, source_df, supabase_client, user_profile)
