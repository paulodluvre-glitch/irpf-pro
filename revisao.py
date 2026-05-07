from __future__ import annotations

from typing import Any


def _metric_delta(history_df, snapshot_df, column: str) -> int | None:
    if history_df.empty:
        return None
    current_date = snapshot_df.loc[0, "data_referencia"].date()
    previous_snapshot = history_df[history_df["data_referencia"].dt.date < current_date].tail(1)
    if previous_snapshot.empty:
        return None
    return int(snapshot_df.iloc[0][column]) - int(previous_snapshot.iloc[0][column])


def _checkpoint_map(checkpoints_df, client_id: int) -> dict[str, dict]:
    if checkpoints_df.empty:
        return {}
    filtered_df = checkpoints_df[checkpoints_df["client_id"] == client_id].copy()
    return {row["step_key"]: row for _, row in filtered_df.iterrows()}


def _get_client_documents_df(documents_df, client_id: int, pd):
    if documents_df.empty or "client_id" not in documents_df.columns:
        return pd.DataFrame()
    return documents_df[documents_df["client_id"] == client_id].copy()


def _normalize_date_to_iso(value, pd) -> str | None:
    if pd.isna(value):
        return None
    return pd.to_datetime(value).date().isoformat()


def _render_general_metrics(st, people_df, history_df, snapshot_df, normalize_text, available_df) -> None:
    counts = people_df["Status Preenchimento"].value_counts()
    metric_1, metric_2, metric_3, metric_4 = st.columns(4)
    metric_5, metric_6, metric_7, metric_8 = st.columns(4)

    transmitted_delta = _metric_delta(history_df, snapshot_df, "transmitidas")
    review_delta = _metric_delta(history_df, snapshot_df, "em_revisao")

    with metric_1:
        st.metric("Total de declarações", len(people_df))
    with metric_2:
        st.metric("Pendentes", int(counts.get("PENDENTE", 0)))
    with metric_3:
        st.metric("Prontas pra preenchimento", len(available_df))
    with metric_4:
        st.metric("Em preenchimento", int(counts.get("EM PREENCHIMENTO", 0)))
    with metric_5:
        st.metric("Em revisão", int(snapshot_df.loc[0, "em_revisao"]), delta=review_delta)
    with metric_6:
        st.metric("Em ajuste", int(counts.get("AJUSTE - HEVERTON", 0)))
    with metric_7:
        st.metric("Transmitidas", int(snapshot_df.loc[0, "transmitidas"]), delta=transmitted_delta)
    with metric_8:
        st.metric("Aguardando reunião", int(counts.get("AGUARDANDO REUNIÃO", 0)))


def _render_analysis_filters(st, people_df, normalize_text):
    filter_col_1, filter_col_2, filter_col_3 = st.columns(3)
    with filter_col_1:
        name_filter = st.text_input("Filtrar por nome", key="review_filter_name")
        group_filter = st.multiselect(
            "Filtrar por grupo",
            options=sorted(people_df["Grupo"].dropna().unique()),
            key="review_filter_group",
        )
    with filter_col_2:
        status_filter = st.multiselect(
            "Status do preenchimento",
            options=sorted(people_df["Status Preenchimento"].dropna().unique()),
            default=sorted(people_df["Status Preenchimento"].dropna().unique()),
            key="review_filter_status",
        )
        documentation_filter = st.multiselect(
            "Status da documentação",
            options=sorted(people_df["Documentação"].dropna().unique()),
            default=sorted(people_df["Documentação"].dropna().unique()),
            key="review_filter_documentation",
        )
    with filter_col_3:
        responsible_filter = st.multiselect(
            "Responsável",
            options=sorted(people_df["Responsável pelo Preenchimento"].dropna().unique()),
            default=sorted(people_df["Responsável pelo Preenchimento"].dropna().unique()),
            key="review_filter_responsible",
        )

    filtered_people_df = people_df.copy()
    if name_filter:
        filtered_people_df = filtered_people_df[
            filtered_people_df["NOME"].map(lambda value: name_filter.upper() in normalize_text(value).upper())
        ].copy()
    if group_filter:
        filtered_people_df = filtered_people_df[filtered_people_df["Grupo"].isin(group_filter)].copy()
    if status_filter:
        filtered_people_df = filtered_people_df[filtered_people_df["Status Preenchimento"].isin(status_filter)].copy()
    if documentation_filter:
        filtered_people_df = filtered_people_df[filtered_people_df["Documentação"].isin(documentation_filter)].copy()
    if responsible_filter:
        filtered_people_df = filtered_people_df[
            filtered_people_df["Responsável pelo Preenchimento"].isin(responsible_filter)
        ].copy()
    return filtered_people_df


def _render_documentation_status(st, pd, people_df) -> None:
    st.markdown("**Status de documentação**")
    documentation_df = people_df.copy()
    documentation_df["Documentos totais"] = documentation_df["total_documentos"].fillna(0).astype(int)
    documentation_df["Documentos recebidos"] = documentation_df["documentos_recebidos"].fillna(0).astype(int)
    documentation_df["faixa_recebimento"] = documentation_df.apply(
        lambda row: "Sem documentação listada"
        if int(row["Documentos totais"]) == 0
        else "Nada recebido"
        if int(row["Documentos recebidos"]) == 0
        else "1% - 25%"
        if (int(row["Documentos recebidos"]) / int(row["Documentos totais"])) * 100 <= 25
        else "26% - 50%"
        if (int(row["Documentos recebidos"]) / int(row["Documentos totais"])) * 100 <= 50
        else "51% - 75%"
        if (int(row["Documentos recebidos"]) / int(row["Documentos totais"])) * 100 <= 75
        else "76% - 100%",
        axis=1,
    )

    metric_1, metric_2, metric_3, metric_4, metric_5, metric_6 = st.columns(6)
    with metric_1:
        st.metric("Sem doc listada", int((documentation_df["faixa_recebimento"] == "Sem documentação listada").sum()))
    with metric_2:
        st.metric("Nada recebido", int((documentation_df["faixa_recebimento"] == "Nada recebido").sum()))
    with metric_3:
        st.metric("1% - 25%", int((documentation_df["faixa_recebimento"] == "1% - 25%").sum()))
    with metric_4:
        st.metric("26% - 50%", int((documentation_df["faixa_recebimento"] == "26% - 50%").sum()))
    with metric_5:
        st.metric("51% - 75%", int((documentation_df["faixa_recebimento"] == "51% - 75%").sum()))
    with metric_6:
        st.metric("76% - 100%", int((documentation_df["faixa_recebimento"] == "76% - 100%").sum()))

    detail_columns = [
        "NOME",
        "Grupo",
        "Nivel de Complexidade",
        "Documentos recebidos",
        "Documentos totais",
        "Recebidos / Total",
        "% documentação recebida",
    ]
    detail_df = documentation_df[detail_columns].copy()
    detail_df["% documentação recebida"] = detail_df["% documentação recebida"].map(lambda value: f"{value:.1f}%")

    status_groups = [
        ("Sem documentação listada", documentation_df["faixa_recebimento"] == "Sem documentação listada"),
        ("Nada recebido", documentation_df["faixa_recebimento"] == "Nada recebido"),
        ("1% - 25%", documentation_df["faixa_recebimento"] == "1% - 25%"),
        ("26% - 50%", documentation_df["faixa_recebimento"] == "26% - 50%"),
        ("51% - 75%", documentation_df["faixa_recebimento"] == "51% - 75%"),
        ("76% - 100%", documentation_df["faixa_recebimento"] == "76% - 100%"),
    ]
    for label, mask in status_groups:
        with st.expander(label):
            subset_df = detail_df[mask].sort_values(["Grupo", "NOME"]).copy()
            if subset_df.empty:
                st.caption("Nenhum cliente nesta faixa.")
            else:
                st.dataframe(subset_df, use_container_width=True, hide_index=True)


def _render_group_progress(st, pd, people_df, status_progress_percent) -> None:
    st.markdown("**Progresso por grupo**")
    progress_df = people_df.copy()
    progress_df["percentual_status"] = progress_df["Status Preenchimento"].map(status_progress_percent)

    group_chart_df = (
        progress_df.groupby("Grupo", dropna=False)["percentual_status"]
        .mean()
        .reset_index()
        .sort_values("percentual_status", ascending=False)
    )
    group_chart_df = group_chart_df.rename(columns={"percentual_status": "Conclusão média (%)"})
    st.bar_chart(group_chart_df.set_index("Grupo"))

    group_options = sorted(progress_df["Grupo"].dropna().unique().tolist())
    if not group_options:
        st.caption("Nenhum grupo disponível para análise.")
        return

    selected_group = st.selectbox("Grupo para detalhar progresso individual", options=group_options, key="review_group_progress_select")
    group_people_df = progress_df[progress_df["Grupo"] == selected_group].copy().sort_values("NOME")
    for _, row in group_people_df.iterrows():
        progress_value = int(row["percentual_status"])
        st.markdown(f"**{row['NOME']}**")
        st.progress(progress_value / 100)
        st.caption(f"Status atual: {row['Status Preenchimento']} | Responsável: {row['Responsável pelo Preenchimento']}")


def _render_review_queue(st, normalize_text, queue_df, title: str) -> None:
    st.markdown(f"**{title}**")
    if queue_df.empty:
        st.info("Nenhuma declaração nesta fila no momento.")
        return
    display_df = queue_df[
        [
            "NOME",
            "Grupo",
            "Status Preenchimento",
            "Responsável pelo Preenchimento",
            "Documentação",
            "Recebidos / Total",
            "documentos_enviados_lista",
            "documentos_faltantes_lista",
            "Data chegada documentação",
            "Data foi para preenchimento",
            "Data chegou para revisão",
        ]
    ].copy().rename(
        columns={
            "documentos_enviados_lista": "Documentos recebidos",
            "documentos_faltantes_lista": "Documentos faltantes",
        }
    )
    display_df["Documentos recebidos"] = display_df["Documentos recebidos"].map(normalize_text)
    display_df["Documentos faltantes"] = display_df["Documentos faltantes"].map(normalize_text)
    st.dataframe(display_df.sort_values(["Grupo", "NOME"]), use_container_width=True, hide_index=True)


def _render_client_summary(st, selected_row) -> None:
    metric_1, metric_2, metric_3, metric_4 = st.columns(4)
    with metric_1:
        st.metric("Documentação", selected_row["Documentação"], selected_row["Recebidos / Total"])
    with metric_2:
        st.metric("Status", selected_row["Status Preenchimento"])
    with metric_3:
        st.metric("Responsável", selected_row["Responsável pelo Preenchimento"])
    with metric_4:
        st.metric("Progresso", selected_row.get("Progresso Geral", "0%"))

    detail_col_1, detail_col_2 = st.columns(2)
    with detail_col_1:
        with st.container(border=True):
            st.markdown("**Documentos recebidos**")
            st.write(selected_row.get("documentos_enviados_lista", "") or "Nenhum documento recebido.")
            st.markdown("**Documentos faltantes**")
            st.write(selected_row.get("documentos_faltantes_lista", "") or "Nenhum documento faltante.")
    with detail_col_2:
        with st.container(border=True):
            st.markdown("**Dados de apoio**")
            st.write(f"Grupo: {selected_row['Grupo']}")
            st.write(f"Nível de complexidade: {selected_row['Nivel de Complexidade']}")
            st.write(f"Telefone: {selected_row.get('Telefone', '') or 'Não informado'}")
            st.write(
                f"Observações gerais da declaração: {selected_row.get('Observações Gerais da Declaração', '') or 'Sem observações.'}"
            )


def _render_review_action_form(
    ctx: dict[str, Any],
    supabase_client,
    selected_row,
    checkpoints_df,
    acting_as: str,
    next_status: str,
    form_key: str,
    observation_step_key: str,
    reviewed_step_key: str,
    observation_label: str,
    final_status_options: list[str] | None = None,
) -> None:
    st = ctx["st"]
    normalize_text = ctx["normalize_text"]
    save_preparation_updates = ctx["save_preparation_updates"]

    client_id = int(selected_row["client_id"])
    checkpoint_map = _checkpoint_map(checkpoints_df, client_id)
    stored_observation = checkpoint_map.get(observation_step_key)
    stored_reviewed = checkpoint_map.get(reviewed_step_key)

    with st.form(form_key):
        reviewed = st.checkbox(
            "Revisado",
            value=bool(stored_reviewed["completed"]) if stored_reviewed is not None else False,
        )
        observation = st.text_area(
            observation_label,
            value=normalize_text(stored_observation["note"]) if stored_observation is not None else "",
            height=140,
        )
        selected_final_status = next_status
        if final_status_options:
            selected_final_status = st.selectbox("Status final", options=final_status_options)
        submitted = st.form_submit_button("Salvar e seguir", use_container_width=True)

    if not submitted:
        return
    if supabase_client is None:
        st.warning("Para salvar a revisão, use o login do Supabase.")
        return
    if not reviewed:
        st.warning("Marque a caixa de revisado para concluir esta etapa.")
        return

    try:
        payload = [
            {
                "step_key": reviewed_step_key,
                "step_label": "Declaração revisada",
                "completed": reviewed,
                "note": "",
            },
            {
                "step_key": observation_step_key,
                "step_label": observation_label,
                "completed": bool(normalize_text(observation)),
                "note": normalize_text(observation),
            },
        ]
        save_preparation_updates(
            supabase_client,
            client_id,
            selected_row["Responsável pelo Preenchimento"],
            selected_final_status,
            acting_as,
            payload,
            allow_checkpoint_updates=True,
        )
        st.toast("Salvo!")
        st.success("Declaração atualizada com sucesso.")
        st.rerun()
    except Exception as exc:
        st.error(f"Não foi possível salvar a revisão: {exc}")


def _render_adjustment_management(
    ctx: dict[str, object],
    supabase_client,
    selected_row,
    people_df,
    documents_df,
    acting_as: str,
    can_manage_records: bool,
) -> None:
    st = ctx["st"]
    pd = ctx["pd"]
    date = ctx["date"]
    normalize_text = ctx["normalize_text"]
    normalize_key = ctx["normalize_key"]
    normalize_cpf = ctx["normalize_cpf"]
    normalize_phone = ctx["normalize_phone"]
    canonical_preparer = ctx.get("canonical_preparer", normalize_text)
    canonical_complexity = ctx.get("canonical_complexity", normalize_text)
    canonical_group_label = ctx.get("canonical_group_label", normalize_text)
    canonical_status = ctx.get("canonical_status", normalize_text)
    status_options = ctx["STATUS_OPTIONS"]
    document_type_options = ctx["DOCUMENT_TYPE_OPTIONS"]
    document_status_options = ctx["DOCUMENT_STATUS_OPTIONS"]
    save_preparation_updates = ctx["save_preparation_updates"]
    save_client_record = ctx["save_client_record"]
    save_document_bulk_updates = ctx["save_document_bulk_updates"]
    save_document_record = ctx["save_document_record"]

    client_id = int(selected_row["client_id"])

    with st.expander("Alterar responsável e status"):
        responsible_names = sorted(
            set(
                people_df["Responsável pelo Preenchimento"].dropna().map(canonical_preparer).tolist()
                + ["Não atribuído", "Paulo", "Valdivone", "Michelle", "Erlane", "Duda", "Malu", "Heverton", "Renato"]
            )
        )
        current_responsible = canonical_preparer(selected_row["Responsável pelo Preenchimento"])
        responsible_options = list(dict.fromkeys([current_responsible, *responsible_names]))
        current_status = canonical_status(selected_row["Status Preenchimento"])
        status_select_options = list(dict.fromkeys([current_status, *status_options]))
        with st.form(f"adjust_status_form_{client_id}"):
            assigned_preparer = st.selectbox("Responsável pelo preenchimento", options=responsible_options, index=0)
            tax_status = st.selectbox("Status da declaração", options=status_select_options, index=0)
            submit_status = st.form_submit_button("Salvar responsável e status", use_container_width=True, disabled=not can_manage_records)
        if submit_status:
            try:
                save_preparation_updates(
                    supabase_client,
                    client_id,
                    assigned_preparer,
                    tax_status,
                    acting_as,
                    [],
                    allow_checkpoint_updates=False,
                )
                st.toast("Salvo!")
                st.success("Responsável e status atualizados.")
                st.rerun()
            except Exception as exc:
                st.error(f"Não foi possível atualizar responsável/status: {exc}")

    with st.expander("Editar cadastro do cliente"):
        with st.form(f"adjust_client_form_{client_id}"):
            col_1, col_2 = st.columns(2)
            with col_1:
                full_name = st.text_input("Nome completo", value=selected_row["NOME"])
                group_name = st.text_input("Grupo", value=selected_row["Grupo"])
                complexity = st.text_input("Nível de complexidade", value=selected_row["Nivel de Complexidade"])
                meeting_status = st.text_input("Reunião", value=selected_row["Reunião"])
            with col_2:
                cpf = st.text_input("CPF", value=selected_row.get("CPF", ""))
                phone = st.text_input("Telefone", value=selected_row.get("Telefone", ""))
                gov_password = st.text_input("Senha Gov", value=selected_row.get("Senha Gov", ""))
                has_digital_certificate = st.checkbox(
                    "Tem certificado digital",
                    value=bool(selected_row.get("Tem Certificado Digital", False)),
                )
                power_of_attorney = st.text_input(
                    "Cadastro de procuração",
                    value=selected_row.get("Cadastro de Procuração", ""),
                )
            submit_client = st.form_submit_button("Salvar cadastro", use_container_width=True, disabled=not can_manage_records)
        if submit_client:
            try:
                save_client_record(
                    supabase_client,
                    {
                        "normalized_name": normalize_key(full_name),
                        "full_name": normalize_text(full_name),
                        "group_name": canonical_group_label(group_name),
                        "meeting_status": normalize_text(meeting_status),
                        "complexity_level": canonical_complexity(complexity),
                        "tax_status": canonical_status(selected_row["Status Preenchimento"]),
                        "assigned_preparer": canonical_preparer(selected_row["Responsável pelo Preenchimento"]),
                        "post_filing_status": normalize_text(selected_row["Status Pós-Envio"]),
                        "documentation_status": normalize_text(selected_row["Documentação"]),
                        "active": True,
                    },
                    {
                        "cpf": normalize_cpf(cpf),
                        "phone": normalize_phone(phone),
                        "gov_password": gov_password,
                        "has_digital_certificate": has_digital_certificate,
                        "power_of_attorney": power_of_attorney,
                    },
                    client_id=client_id,
                )
                st.toast("Salvo!")
                st.success("Cadastro atualizado.")
                st.rerun()
            except Exception as exc:
                st.error(f"Não foi possível atualizar cadastro: {exc}")

    with st.expander("Documentos faltantes e observações"):
        client_documents_df = _get_client_documents_df(documents_df, client_id, pd)
        if client_documents_df.empty:
            st.caption("Esse cliente ainda não tem documentos cadastrados.")
        else:
            editor_df = client_documents_df[["document_id", "documento_descricao", "Status", "Última Atualização", "Observação Documento"]].copy()
            editor_df = editor_df.rename(columns={"documento_descricao": "Documento", "Observação Documento": "Observação"})
            editor_df["Última Atualização"] = pd.to_datetime(editor_df["Última Atualização"], errors="coerce").dt.date
            status_choices = list(dict.fromkeys(client_documents_df["Status"].dropna().map(normalize_text).tolist() + document_status_options))
            edited_docs_df = st.data_editor(
                editor_df,
                use_container_width=True,
                hide_index=True,
                disabled=["document_id", "Documento", "Última Atualização"],
                column_config={
                    "Status": st.column_config.SelectboxColumn("Status", options=status_choices),
                    "Última Atualização": st.column_config.DateColumn("Última atualização", format="DD/MM/YYYY"),
                    "Observação": st.column_config.TextColumn("Observação do documento"),
                },
                key=f"adjust_docs_editor_{client_id}",
            )
            if st.button(
                "Salvar documentos e observações",
                use_container_width=True,
                disabled=not can_manage_records,
                key=f"adjust_save_docs_{client_id}",
            ):
                try:
                    original_dates = {int(row["document_id"]): row["Última Atualização"] for _, row in editor_df.iterrows()}
                    updates = []
                    for _, row in edited_docs_df.iterrows():
                        document_id = int(row["document_id"])
                        status = normalize_text(row.get("Status", "")).upper() or "SEM STATUS"
                        last_update = original_dates.get(document_id)
                        if status == "RECEBIDO" and pd.isna(last_update):
                            last_update = date.today()
                        updates.append(
                            {
                                "document_id": document_id,
                                "Status": status,
                                "last_update": _normalize_date_to_iso(last_update, pd),
                                "Observação Documento": row.get("Observação", ""),
                            }
                        )
                    save_document_bulk_updates(supabase_client, updates, client_id)
                    st.toast("Salvo!")
                    st.success("Documentos atualizados para o Comercial cobrar o que faltar.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Não foi possível atualizar documentos: {exc}")

        st.markdown("**Adicionar documento faltante**")
        with st.form(f"adjust_add_doc_{client_id}"):
            col_1, col_2 = st.columns(2)
            with col_1:
                document_type = st.selectbox("Tipo de documento", options=document_type_options, key=f"adjust_new_doc_type_{client_id}")
                institution = st.text_input("Instituição", key=f"adjust_new_doc_institution_{client_id}")
                status = st.selectbox(
                    "Status do documento",
                    options=document_status_options,
                    index=document_status_options.index("SOLICITAR DOCUMENTO")
                    if "SOLICITAR DOCUMENTO" in document_status_options
                    else 0,
                    key=f"adjust_new_doc_status_{client_id}",
                )
            with col_2:
                last_update = st.date_input("Última atualização", value=date.today(), key=f"adjust_new_doc_date_{client_id}")
                control_key = st.text_input("Chave de controle", key=f"adjust_new_doc_control_{client_id}")
                notes = st.text_area("Observação do documento", height=90, key=f"adjust_new_doc_note_{client_id}")
            add_doc = st.form_submit_button("Adicionar documento", use_container_width=True, disabled=not can_manage_records)
        if add_doc:
            try:
                save_document_record(
                    supabase_client,
                    client_id=client_id,
                    document_type=document_type,
                    institution=institution,
                    status=status,
                    last_update=last_update,
                    control_key=control_key,
                    notes=notes,
                )
                st.toast("Salvo!")
                st.success("Documento faltante adicionado e disponível para cobrança no Comercial.")
                st.rerun()
            except Exception as exc:
                st.error(f"Não foi possível adicionar documento: {exc}")


def render_review_page(
    ctx: dict[str, Any],
    people_df,
    snapshot_df,
    supabase_client,
    checkpoints_df,
    documents_df,
    user_profile: dict[str, object],
) -> None:
    st = ctx["st"]
    pd = ctx["pd"]
    normalize_text = ctx["normalize_text"]
    build_available_preparation_queue = ctx["build_available_preparation_queue"]
    status_progress_percent = ctx["status_progress_percent"]
    load_history_remote = ctx["load_history_remote"]
    load_history = ctx["load_history"]
    save_snapshot_remote = ctx["save_snapshot_remote"]
    save_snapshot = ctx["save_snapshot"]

    st.header("Revisão")
    acting_as = normalize_text(user_profile.get("display_name", "")) or "Equipe"
    can_manage_records = bool(user_profile.get("can_manage_records", False))

    analysis_tab, review_tab, adjustments_tab = st.tabs(["Análise Geral", "Revisão", "Ajustes"])

    with analysis_tab:
        history_df = load_history_remote(supabase_client) if supabase_client is not None else load_history()
        available_df = build_available_preparation_queue(people_df)
        _render_general_metrics(st, people_df, history_df, snapshot_df, normalize_text, available_df)
        filtered_people_df = _render_analysis_filters(st, people_df, normalize_text)

        consolidated_df = filtered_people_df[
            [
                "NOME",
                "Grupo",
                "Status Preenchimento",
                "Documentação",
                "Recebidos / Total",
                "documentos_enviados_lista",
                "documentos_faltantes_lista",
                "Responsável pelo Preenchimento",
                "Progresso Geral",
                "last_activity_at",
                "Data chegada documentação",
                "Data foi para preenchimento",
                "Data chegou para revisão",
                "Data foi para ajuste",
                "Data transmissão",
                "Data aguardando reunião",
            ]
        ].copy().rename(
            columns={
                "documentos_enviados_lista": "Documentos recebidos",
                "documentos_faltantes_lista": "Documentos faltantes",
            }
        )
        st.dataframe(consolidated_df.sort_values(["Status Preenchimento", "Grupo", "NOME"]), use_container_width=True, hide_index=True)

        export_review_df = consolidated_df.copy()
        for column in ["Documentos recebidos", "Documentos faltantes"]:
            export_review_df[column] = export_review_df[column].map(lambda value: normalize_text(str(value).replace("\n", " | ")))
        st.download_button(
            "Exportar tabela da revisão",
            data=export_review_df.to_csv(index=False, sep=";").encode("utf-8-sig"),
            file_name="revisao_filtrada.csv",
            mime="text/csv",
        )

        st.divider()
        _render_documentation_status(st, pd, people_df)
        st.divider()
        _render_group_progress(st, pd, people_df, status_progress_percent)

        if st.button("Salvar posição do dia", use_container_width=True, key="review_save_snapshot"):
            if supabase_client is not None:
                save_snapshot_remote(supabase_client, snapshot_df)
            else:
                save_snapshot(snapshot_df)
            st.success("Snapshot salvo.")

    with review_tab:
        review_queue_df = people_df[people_df["Status Preenchimento"] == "PRONTO PARA REVISÃO"].copy()
        _render_review_queue(st, normalize_text, review_queue_df, "Fila de revisão do Renato")
        if not review_queue_df.empty:
            selected_name = st.selectbox(
                "Selecione uma declaração para revisar",
                options=review_queue_df.sort_values("NOME")["NOME"].tolist(),
                key="review_queue_select",
            )
            selected_row = review_queue_df[review_queue_df["NOME"] == selected_name].iloc[0]
            _render_client_summary(st, selected_row)
            _render_review_action_form(
                ctx,
                supabase_client,
                selected_row,
                checkpoints_df,
                acting_as,
                next_status="AJUSTE - HEVERTON",
                form_key=f"review_form_{int(selected_row['client_id'])}",
                observation_step_key="renato_observacoes",
                reviewed_step_key="renato_revisado",
                observation_label="Observações gerais para o Heverton",
            )

    with adjustments_tab:
        adjust_queue_df = people_df[people_df["Status Preenchimento"] == "AJUSTE - HEVERTON"].copy()
        _render_review_queue(st, normalize_text, adjust_queue_df, "Fila de ajustes do Heverton")
        if not adjust_queue_df.empty:
            selected_name = st.selectbox(
                "Selecione uma declaração para ajustar",
                options=adjust_queue_df.sort_values("NOME")["NOME"].tolist(),
                key="adjust_queue_select",
            )
            selected_row = adjust_queue_df[adjust_queue_df["NOME"] == selected_name].iloc[0]
            _render_client_summary(st, selected_row)
            _render_adjustment_management(
                ctx,
                supabase_client,
                selected_row,
                people_df,
                documents_df,
                acting_as,
                can_manage_records,
            )
            _render_review_action_form(
                ctx,
                supabase_client,
                selected_row,
                checkpoints_df,
                acting_as,
                next_status="TRANSMITIDO",
                form_key=f"adjust_form_{int(selected_row['client_id'])}",
                observation_step_key="heverton_observacoes",
                reviewed_step_key="heverton_revisado",
                observation_label="Observações gerais finais",
                final_status_options=["TRANSMITIDO", "AGUARDANDO REUNIÃO"],
            )
