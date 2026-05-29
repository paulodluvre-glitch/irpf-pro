from __future__ import annotations

from typing import Any


POST_FILING_NOTE_STEP_KEY = "pos_envio_observacoes"
DISPLAY_COLUMNS = [
    "CPF",
    "NOME",
    "Status Preenchimento",
    "Status Pós-Envio",
    "Cadastro de Procuração",
]
EXPORT_COLUMNS = ["client_id", *DISPLAY_COLUMNS]


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
    canonical_status = ctx["canonical_status"]
    declaration_status_options = ctx["STATUS_OPTIONS"]

    filter_cols = st.columns([1.2, 1.2, 1.2, 1.6])
    with filter_cols[0]:
        selected_statuses = st.multiselect(
            "Status pós-envio",
            options=status_options,
            default=status_options,
        )
    with filter_cols[1]:
        current_declaration_statuses = source_df["Status Preenchimento"].map(canonical_status)
        available_declaration_statuses = [
            status for status in declaration_status_options if status in set(current_declaration_statuses)
        ]
        selected_declaration_statuses = st.multiselect(
            "Status preenchimento",
            options=available_declaration_statuses,
            default=available_declaration_statuses,
        )
    with filter_cols[2]:
        group_options = sorted(
            [group for group in source_df["Grupo"].dropna().map(normalize_text).unique().tolist() if group]
        )
        selected_groups = st.multiselect("Grupo", options=group_options)
    with filter_cols[3]:
        name_filter = st.text_input("Buscar por nome", placeholder="Digite parte do nome do cliente")

    filtered_df = source_df.copy()
    filtered_df["Status Preenchimento"] = filtered_df["Status Preenchimento"].map(canonical_status)
    if selected_statuses:
        filtered_df = filtered_df[filtered_df["Status Pós-Envio"].isin(selected_statuses)]
    if selected_declaration_statuses:
        filtered_df = filtered_df[filtered_df["Status Preenchimento"].isin(selected_declaration_statuses)]
    if selected_groups:
        filtered_df = filtered_df[filtered_df["Grupo"].isin(selected_groups)]
    if normalize_text(name_filter):
        needle = normalize_text(name_filter).lower()
        filtered_df = filtered_df[filtered_df["NOME"].map(lambda value: needle in normalize_text(value).lower())]
    return filtered_df


def _render_metrics(ctx: dict[str, Any], source_df, status_options: list[str]) -> None:
    st = ctx["st"]
    canonical_status = ctx["canonical_status"]
    counts = source_df["Status Pós-Envio"].value_counts()
    total_declarations = len(source_df)
    transmitted_total = int(source_df["Status Preenchimento"].map(canonical_status).eq("TRANSMITIDO").sum())

    _, transmitted_col, total_col, _ = st.columns([1, 1.25, 1.25, 1])
    with transmitted_col:
        st.metric("Transmitidas", transmitted_total)
    with total_col:
        st.metric("Total de declarações na base", total_declarations)

    st.caption("Status pós-envio")
    status_columns = st.columns(len(status_options))
    for column, status in zip(status_columns, status_options):
        with column:
            st.caption(status)
            st.markdown(f"### {int(counts.get(status, 0))}")


def _build_table_export(ctx: dict[str, Any], filtered_df):
    normalize_text = ctx["normalize_text"]
    available_columns = [column for column in EXPORT_COLUMNS if column in filtered_df.columns]
    export_df = filtered_df[available_columns].copy()
    if "client_id" in export_df.columns:
        export_df = export_df.rename(columns={"client_id": "id"})
    for column in export_df.columns:
        export_df[column] = export_df[column].map(normalize_text)
    return export_df.sort_values(["Status Pós-Envio", "NOME"]) if not export_df.empty else export_df


def _render_detail_table(ctx: dict[str, Any], filtered_df) -> None:
    st = ctx["st"]

    available_columns = [column for column in DISPLAY_COLUMNS if column in filtered_df.columns]
    display_df = filtered_df[available_columns].copy()
    export_df = _build_table_export(ctx, filtered_df)

    st.dataframe(
        display_df.sort_values(["Status Pós-Envio", "NOME"]),
        use_container_width=True,
        hide_index=True,
    )
    st.download_button(
        "Exportar tabela filtrada",
        data=export_df.to_csv(index=False, sep=";").encode("utf-8-sig"),
        file_name="pos_envio_filtrado.csv",
        mime="text/csv",
        use_container_width=True,
        disabled=export_df.empty,
    )


def _render_editor(ctx: dict[str, Any], source_df, supabase_client, user_profile: dict[str, object]) -> None:
    st = ctx["st"]
    normalize_text = ctx["normalize_text"]
    normalize_cpf = ctx["normalize_cpf"]
    canonical_status = ctx["canonical_status"]
    canonical_post_filing_status = ctx["canonical_post_filing_status"]
    declaration_status_options = ctx["STATUS_OPTIONS"]
    status_options = ctx["POST_FILING_STATUS_OPTIONS"]
    save_post_filing_update = ctx["save_post_filing_update"]
    can_manage_records = bool(user_profile.get("can_manage_records", False))

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
        "Cliente da tabela filtrada",
        options=client_ids,
        format_func=lambda client_id: (
            f"{normalize_text(client_lookup[client_id]['NOME'])} | {normalize_text(client_lookup[client_id]['Grupo'])}"
        ),
    )
    selected_row = client_lookup[selected_client_id]
    current_declaration_status = canonical_status(selected_row.get("Status Preenchimento", ""))
    current_post_status = canonical_post_filing_status(selected_row.get("Status Pós-Envio", ""))
    current_observation = normalize_text(selected_row.get("Observação Pós-Envio", ""))

    info_cols = st.columns(5)
    info_cols[0].caption("CPF")
    info_cols[0].write(normalize_text(selected_row.get("CPF", "")) or "Não informado")
    info_cols[1].caption("Nome")
    info_cols[1].write(normalize_text(selected_row.get("NOME", "")) or "Não informado")
    info_cols[2].caption("Status preenchimento")
    info_cols[2].write(current_declaration_status)
    info_cols[3].caption("Status pós-envio")
    info_cols[3].write(current_post_status)
    info_cols[4].caption("Procuração")
    info_cols[4].write(normalize_text(selected_row.get("Cadastro de Procuração", "")) or "Não informado")

    if not can_manage_records:
        st.info("Seu usuário pode consultar essa tela, mas não está liberado para salvar alterações cadastrais.")

    with st.form(f"post_filing_form_{selected_client_id}"):
        col_a, col_b = st.columns(2)
        with col_a:
            full_name = st.text_input("NOME", value=normalize_text(selected_row.get("NOME", "")))
            cpf = st.text_input("CPF", value=normalize_cpf(selected_row.get("CPF", "")))
            tax_status = st.selectbox(
                "Status Preenchimento",
                options=declaration_status_options,
                index=(
                    declaration_status_options.index(current_declaration_status)
                    if current_declaration_status in declaration_status_options
                    else declaration_status_options.index("SEM STATUS")
                ),
            )
        with col_b:
            status = st.selectbox(
                "Status Pós-Envio",
                options=status_options,
                index=(
                    status_options.index(current_post_status)
                    if current_post_status in status_options
                    else status_options.index("STATUS A VERIFICAR")
                ),
            )
            power_of_attorney = st.text_input(
                "Cadastro de Procuração",
                value=normalize_text(selected_row.get("Cadastro de Procuração", "")),
            )
        observation = st.text_area(
            "Observações do pós-envio",
            value=current_observation,
            height=120,
            placeholder="Ex.: aguardando processamento no e-CAC, pendência conferida, retorno do cliente...",
        )
        submitted = st.form_submit_button(
            "Salvar alterações",
            use_container_width=True,
            disabled=not can_manage_records,
        )

    if submitted:
        if not normalize_text(full_name):
            st.error("Informe o nome do cliente antes de salvar.")
            return
        try:
            save_post_filing_update(
                supabase_client,
                selected_client_id,
                status,
                observation,
                normalize_text(user_profile.get("display_name", "")) or "Sistema",
                full_name=full_name,
                cpf=cpf,
                tax_status=tax_status,
                power_of_attorney=power_of_attorney,
            )
            st.toast("Salvo!")
            st.success("Cadastro e pós-envio atualizados.")
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
    _render_editor(ctx, filtered_df, supabase_client, user_profile)
