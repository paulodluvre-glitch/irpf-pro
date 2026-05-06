from __future__ import annotations

from typing import Any


def _normalized(value: object, normalize_text) -> str:
    return normalize_text(value).upper()


def _is_unassigned(value: object, normalize_text) -> bool:
    return _normalized(value, normalize_text) in {"", "NÃO ATRIBUÍDO", "NAO ATRIBUIDO"}


def _build_checkpoint_map(checkpoints_df, client_id: int) -> dict[str, dict]:
    if checkpoints_df.empty:
        return {}
    filtered_df = checkpoints_df[checkpoints_df["client_id"] == client_id].copy()
    return {row["step_key"]: row for _, row in filtered_df.iterrows()}


def _build_my_df(people_df, acting_as: str, normalize_text):
    acting_key = _normalized(acting_as, normalize_text)
    return people_df[
        people_df["Responsável pelo Preenchimento"].map(lambda value: _normalized(value, normalize_text) == acting_key)
    ].copy()


def _get_client_documents_df(documents_df, client_id: int, pd):
    if "client_id" not in documents_df.columns:
        return pd.DataFrame()
    return documents_df[documents_df["client_id"] == client_id].copy()


def _normalize_date_to_iso(value, pd) -> str | None:
    if pd.isna(value):
        return None
    return pd.to_datetime(value).date().isoformat()


def _assigned_options(team_df, normalize_text) -> list[str]:
    names = set(team_df["name"].dropna().map(normalize_text).tolist()) if "name" in team_df.columns else set()
    names.update(["Wanessa", "Paulo", "Valdivone", "Michelle", "Erlane", "Duda", "Malu", "Heverton", "Renato"])
    return ["Não atribuído"] + sorted(name for name in names if name)


def _render_queue_table(st, queue_df) -> None:
    if queue_df.empty:
        st.info("Nenhuma declaração disponível neste momento.")
        return
    display_df = queue_df[
        [
            "NOME",
            "Grupo",
            "Nivel de Complexidade",
            "Documentação",
            "Status para Preenchimento",
            "Recebidos / Total",
            "% documentação recebida",
        ]
    ].copy()
    display_df["% documentação recebida"] = display_df["% documentação recebida"].map(lambda value: f"{value:.1f}%")
    display_df = display_df.rename(columns={"% documentação recebida": "% recebido"})
    st.dataframe(
        display_df.sort_values(["Grupo", "Nivel de Complexidade", "NOME"]),
        use_container_width=True,
        hide_index=True,
    )


def _render_my_table(st, my_df) -> None:
    if my_df.empty:
        st.info("Você ainda não tem declarações atribuídas.")
        return
    display_df = my_df[
        [
            "NOME",
            "Grupo",
            "Nivel de Complexidade",
            "Documentação",
            "Status Preenchimento",
            "Recebidos / Total",
            "Progresso Geral",
            "last_activity_at",
        ]
    ].copy()
    st.dataframe(
        display_df.sort_values(["Status Preenchimento", "Grupo", "NOME"]),
        use_container_width=True,
        hide_index=True,
    )


def _render_general_table(st, people_df, normalize_text):
    filtered_df = people_df.copy()
    filter_col_1, filter_col_2, filter_col_3 = st.columns(3)
    with filter_col_1:
        name_filter = st.text_input("Nome", key="prep_general_name_filter")
        group_filter = st.multiselect(
            "Grupo",
            options=sorted(filtered_df["Grupo"].dropna().unique()),
            key="prep_general_group_filter",
        )
    with filter_col_2:
        status_filter = st.multiselect(
            "Status",
            options=sorted(filtered_df["Status Preenchimento"].dropna().unique()),
            key="prep_general_status_filter",
        )
        documentation_filter = st.multiselect(
            "Documentação",
            options=sorted(filtered_df["Documentação"].dropna().unique()),
            key="prep_general_documentation_filter",
        )
    with filter_col_3:
        responsible_filter = st.multiselect(
            "Responsável",
            options=sorted(filtered_df["Responsável pelo Preenchimento"].dropna().unique()),
            key="prep_general_responsible_filter",
        )
        complexity_filter = st.multiselect(
            "Complexidade",
            options=sorted(filtered_df["Nivel de Complexidade"].dropna().unique()),
            key="prep_general_complexity_filter",
        )

    if name_filter:
        filtered_df = filtered_df[filtered_df["NOME"].map(lambda value: normalize_text(name_filter).upper() in normalize_text(value).upper())].copy()
    if group_filter:
        filtered_df = filtered_df[filtered_df["Grupo"].isin(group_filter)].copy()
    if status_filter:
        filtered_df = filtered_df[filtered_df["Status Preenchimento"].isin(status_filter)].copy()
    if documentation_filter:
        filtered_df = filtered_df[filtered_df["Documentação"].isin(documentation_filter)].copy()
    if responsible_filter:
        filtered_df = filtered_df[filtered_df["Responsável pelo Preenchimento"].isin(responsible_filter)].copy()
    if complexity_filter:
        filtered_df = filtered_df[filtered_df["Nivel de Complexidade"].isin(complexity_filter)].copy()

    display_columns = [
        "NOME",
        "Grupo",
        "Nivel de Complexidade",
        "Documentação",
        "Recebidos / Total",
        "Status Preenchimento",
        "Responsável pelo Preenchimento",
        "Progresso Geral",
        "Data chegada documentação",
        "Data foi para preenchimento",
        "Data chegou para revisão",
    ]
    display_columns = [column for column in display_columns if column in filtered_df.columns]
    st.dataframe(
        filtered_df[display_columns].sort_values(["Status Preenchimento", "Grupo", "NOME"]),
        use_container_width=True,
        hide_index=True,
    )
    return filtered_df


def _render_client_header(st, selected_row) -> None:
    summary_col_1, summary_col_2, summary_col_3, summary_col_4 = st.columns(4)
    with summary_col_1:
        st.metric("Documentação", selected_row["Documentação"], selected_row["Recebidos / Total"])
    with summary_col_2:
        st.metric("Status", selected_row["Status Preenchimento"])
    with summary_col_3:
        st.metric("Responsável", selected_row["Responsável pelo Preenchimento"])
    with summary_col_4:
        st.metric("Progresso", selected_row.get("Progresso Geral", "0%"))


def _render_support_panels(st, selected_row) -> None:
    info_col_1, info_col_2 = st.columns(2)
    with info_col_1:
        with st.container(border=True):
            st.markdown("**Documentos recebidos e faltantes**")
            st.caption("Recebidos")
            st.write(selected_row.get("documentos_enviados_lista", "") or "Nenhum documento marcado como recebido.")
            st.caption("Faltantes")
            st.write(selected_row.get("documentos_faltantes_lista", "") or "Nenhum documento faltante.")
    with info_col_2:
        with st.container(border=True):
            st.markdown("**Dados de apoio**")
            st.write(f"Grupo: {selected_row['Grupo']}")
            st.write(f"Nível de complexidade: {selected_row['Nivel de Complexidade']}")
            st.write(f"CPF: {selected_row.get('CPF', '') or 'Não informado'}")
            st.write(f"Telefone: {selected_row.get('Telefone', '') or 'Não informado'}")
            st.write(f"Senha Gov: {selected_row.get('Senha Gov', '') or 'Não informada'}")
            st.write(
                "Certificado digital: "
                + ("Sim" if bool(selected_row.get("Tem Certificado Digital", False)) else "Não")
            )
            st.write(f"Procuração: {selected_row.get('Cadastro de Procuração', '') or 'Não informada'}")
            st.write(
                "Observações gerais atuais: "
                + (selected_row.get("Observações Gerais da Declaração", "") or "Sem observações registradas.")
            )


def _render_general_client_admin(
    ctx: dict[str, Any],
    supabase_client,
    selected_row,
    checkpoints_df,
    documents_df,
    team_df,
    acting_as: str,
    can_edit_preparation: bool,
    can_manage_documents: bool,
) -> None:
    st = ctx["st"]
    pd = ctx["pd"]
    date = ctx["date"]
    normalize_text = ctx["normalize_text"]
    status_options_base = ctx["STATUS_OPTIONS"]
    document_type_options = ctx["DOCUMENT_TYPE_OPTIONS"]
    document_status_options = ctx["DOCUMENT_STATUS_OPTIONS"]
    save_preparation_updates = ctx["save_preparation_updates"]
    save_document_bulk_updates = ctx["save_document_bulk_updates"]
    save_document_record = ctx["save_document_record"]
    update_document_record = ctx["update_document_record"]
    delete_document_record = ctx["delete_document_record"]

    client_id = int(selected_row["client_id"])
    checkpoint_map = _build_checkpoint_map(checkpoints_df, client_id)
    assigned_options = _assigned_options(team_df, normalize_text)
    current_responsible = normalize_text(selected_row["Responsável pelo Preenchimento"]) or "Não atribuído"
    current_status = normalize_text(selected_row["Status Preenchimento"]) or "SEM STATUS"
    responsible_options = list(dict.fromkeys([current_responsible, *assigned_options]))
    status_options = list(dict.fromkeys([current_status, *status_options_base]))

    st.markdown("**Transferência e observações**")
    with st.form(f"prep_general_client_form_{client_id}"):
        col_1, col_2 = st.columns(2)
        with col_1:
            assigned_preparer = st.selectbox(
                "Responsável pelo preenchimento",
                options=responsible_options,
                index=0,
                disabled=not can_edit_preparation,
            )
            tax_status = st.selectbox(
                "Status da declaração",
                options=status_options,
                index=0,
                disabled=not can_edit_preparation,
            )
        with col_2:
            observation_state = checkpoint_map.get("observacoes_gerais")
            general_observation = st.text_area(
                "Observações Gerais da Declaração / documentos faltantes",
                value=normalize_text(observation_state["note"]) if observation_state is not None else "",
                height=130,
                disabled=not can_edit_preparation,
            )
        submitted = st.form_submit_button(
            "Salvar transferência e observações",
            use_container_width=True,
            disabled=not can_edit_preparation,
        )

    if submitted:
        if supabase_client is None:
            st.warning("Para salvar, use o login do Supabase.")
        else:
            try:
                payload = [
                    {
                        "step_key": "observacoes_gerais",
                        "step_label": "Observações gerais da declaração",
                        "completed": bool(normalize_text(general_observation)),
                        "note": normalize_text(general_observation),
                    }
                ]
                save_preparation_updates(
                    supabase_client,
                    client_id,
                    assigned_preparer,
                    tax_status,
                    acting_as,
                    payload,
                    allow_checkpoint_updates=True,
                )
                st.toast("Salvo!")
                st.success("Responsável, status e observações atualizados.")
                st.rerun()
            except Exception as exc:
                st.error(f"Não foi possível salvar a atualização: {exc}")

    st.markdown("**Documentos e solicitações**")
    client_documents_df = _get_client_documents_df(documents_df, client_id, pd)
    if client_documents_df.empty:
        st.caption("Esse cliente ainda não tem documentos cadastrados.")
    else:
        editor_df = client_documents_df[["document_id", "documento_descricao", "Status", "Última Atualização"]].copy()
        editor_df = editor_df.rename(columns={"documento_descricao": "Documento"})
        editor_df["Última Atualização"] = pd.to_datetime(editor_df["Última Atualização"], errors="coerce").dt.date
        editor_status_options = list(dict.fromkeys(client_documents_df["Status"].dropna().map(normalize_text).tolist() + document_status_options))
        edited_docs_df = st.data_editor(
            editor_df,
            use_container_width=True,
            hide_index=True,
            disabled=["document_id", "Documento", "Última Atualização"],
            column_config={
                "Status": st.column_config.SelectboxColumn("Status", options=editor_status_options),
                "Última Atualização": st.column_config.DateColumn("Última atualização", format="DD/MM/YYYY"),
            },
            key=f"prep_general_docs_editor_{client_id}",
        )
        if st.button(
            "Salvar status dos documentos",
            use_container_width=True,
            disabled=not can_manage_documents,
            key=f"prep_general_save_docs_{client_id}",
        ):
            try:
                original_dates = {
                    int(row["document_id"]): row["Última Atualização"]
                    for _, row in editor_df.iterrows()
                }
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
                        }
                    )
                save_document_bulk_updates(supabase_client, updates, client_id)
                st.toast("Salvo!")
                st.success("Status dos documentos atualizado.")
                st.rerun()
            except Exception as exc:
                st.error(f"Não foi possível atualizar os documentos: {exc}")

    with st.expander("Adicionar, editar ou remover documento"):
        with st.form(f"prep_general_document_add_{client_id}"):
            add_col_1, add_col_2 = st.columns(2)
            with add_col_1:
                new_document_type = st.selectbox("Tipo de documento", options=document_type_options, key=f"prep_general_new_type_{client_id}")
                new_institution = st.text_input("Instituição", key=f"prep_general_new_institution_{client_id}")
                new_status = st.selectbox("Status do documento", options=document_status_options, key=f"prep_general_new_status_{client_id}")
            with add_col_2:
                new_last_update = st.date_input("Última atualização", value=date.today(), key=f"prep_general_new_last_update_{client_id}")
                new_control_key = st.text_input("Chave de controle", key=f"prep_general_new_control_{client_id}")
            add_document = st.form_submit_button("Adicionar documento", use_container_width=True, disabled=not can_manage_documents)

        if add_document:
            try:
                save_document_record(
                    supabase_client,
                    client_id=client_id,
                    document_type=new_document_type,
                    institution=new_institution,
                    status=new_status,
                    last_update=new_last_update,
                    control_key=new_control_key,
                )
                st.toast("Salvo!")
                st.success("Documento adicionado.")
                st.rerun()
            except Exception as exc:
                st.error(f"Não foi possível adicionar o documento: {exc}")

        if not client_documents_df.empty and "document_id" in client_documents_df.columns:
            editable_docs = {
                f"{row['Tipo Documento']} - {row['Instituição']} ({row['Status']})": row
                for _, row in client_documents_df.sort_values(["Tipo Documento", "Instituição"]).iterrows()
            }
            selected_doc_label = st.selectbox("Documento para editar/remover", options=list(editable_docs.keys()), key=f"prep_general_doc_select_{client_id}")
            selected_doc_row = editable_docs[selected_doc_label]
            with st.form(f"prep_general_document_edit_{client_id}_{int(selected_doc_row['document_id'])}"):
                edit_col_1, edit_col_2 = st.columns(2)
                with edit_col_1:
                    edit_type_options = list(dict.fromkeys([selected_doc_row["Tipo Documento"], *document_type_options]))
                    edit_document_type = st.selectbox("Tipo de documento atual", options=edit_type_options, index=0)
                    edit_institution = st.text_input("Instituição atual", value=selected_doc_row["Instituição"])
                    edit_status_options = list(dict.fromkeys([selected_doc_row["Status"], *document_status_options]))
                    edit_status = st.selectbox("Status atual", options=edit_status_options, index=0)
                with edit_col_2:
                    existing_doc_date = selected_doc_row["Última Atualização"]
                    existing_doc_date = date.today() if pd.isna(existing_doc_date) else pd.to_datetime(existing_doc_date).date()
                    edit_last_update = st.date_input("Última atualização atual", value=existing_doc_date)
                    edit_control_key = st.text_input("Chave de controle atual", value=selected_doc_row["chave_controle"])
                update_document = st.form_submit_button("Salvar alteração do documento", use_container_width=True, disabled=not can_manage_documents)

            if update_document:
                try:
                    update_document_record(
                        supabase_client,
                        document_id=int(selected_doc_row["document_id"]),
                        client_id=client_id,
                        document_type=edit_document_type,
                        institution=edit_institution,
                        status=edit_status,
                        last_update=edit_last_update,
                        control_key=edit_control_key,
                    )
                    st.toast("Salvo!")
                    st.success("Documento atualizado.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Não foi possível atualizar o documento: {exc}")

            if st.button(
                "Remover documento selecionado",
                use_container_width=True,
                type="secondary",
                disabled=not can_manage_documents,
                key=f"prep_general_remove_doc_{int(selected_doc_row['document_id'])}",
            ):
                try:
                    delete_document_record(supabase_client, int(selected_doc_row["document_id"]), client_id)
                    st.toast("Excluído!")
                    st.success("Documento removido.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Não foi possível remover o documento: {exc}")


def _render_preparation_form(
    ctx: dict[str, Any],
    supabase_client,
    selected_row,
    checkpoints_df,
    documents_df,
    acting_as: str,
    can_edit_preparation: bool,
    can_edit_full_preparation: bool,
    prefix: str,
) -> None:
    st = ctx["st"]
    normalize_text = ctx["normalize_text"]
    status_options_base = ctx["STATUS_OPTIONS"]
    preparation_steps = ctx["PREPARATION_STEPS"]
    available_statuses = ctx["AVAILABLE_DECLARATION_STATUSES"]
    build_document_sections = ctx["build_document_sections"]
    save_preparation_updates = ctx["save_preparation_updates"]

    client_id = int(selected_row["client_id"])
    checkpoint_map = _build_checkpoint_map(checkpoints_df, client_id)
    document_sections = build_document_sections(documents_df=documents_df, checkpoints_df=checkpoints_df, client_id=client_id)

    st.markdown("**Atualização do preenchimento**")
    with st.form(f"{prefix}_preparation_form_{client_id}"):
        current_responsible = selected_row["Responsável pelo Preenchimento"]
        assume_default = _is_unassigned(current_responsible, normalize_text)
        assume_responsibility = st.checkbox(
            "Assumir a responsabilidade desta declaração para mim",
            value=assume_default,
            disabled=not can_edit_preparation,
        )

        default_status = (
            "EM PREENCHIMENTO"
            if normalize_text(selected_row["Status Preenchimento"]) in available_statuses
            else selected_row["Status Preenchimento"]
        )
        status_options = status_options_base + sorted(
            status
            for status in selected_row.to_frame().T["Status Preenchimento"].dropna().unique()
            if status not in status_options_base
        )
        selected_status = st.selectbox(
            "Status do preenchimento",
            options=status_options,
            index=status_options.index(default_status) if default_status in status_options else 0,
            disabled=not can_edit_preparation,
        )

        st.markdown("**Confirmações gerais**")
        payload: list[dict] = []
        for step_key, step_label in preparation_steps:
            stored = checkpoint_map.get(step_key)
            completed = st.radio(
                step_label,
                options=["Sim", "Não"],
                index=0 if stored is not None and bool(stored["completed"]) else 1,
                horizontal=True,
                key=f"{prefix}_{client_id}_{step_key}_completed",
                disabled=not can_edit_full_preparation,
            ) == "Sim"
            note_label = "Observação"
            if step_key == "dividas_emprestimos":
                note_label = "Se sim, especifique o que"
            note = st.text_input(
                f"{note_label} - {step_label}",
                value=normalize_text(stored["note"]) if stored is not None else "",
                key=f"{prefix}_{client_id}_{step_key}_note",
                disabled=not can_edit_full_preparation,
            )
            payload.append(
                {
                    "step_key": step_key,
                    "step_label": step_label,
                    "completed": completed,
                    "note": normalize_text(note),
                }
            )

        st.markdown("**Lançamento dos documentos na declaração**")
        if not document_sections:
            st.caption("Nenhum documento cadastrado para este cliente.")
        for section in document_sections:
            with st.container(border=True):
                st.markdown(f"**{section['section_label']}**")
                columns = st.columns(2)
                for index, item in enumerate(section["items"]):
                    with columns[index % 2]:
                        launched = st.checkbox(
                            item["step_label"],
                            value=item["completed"],
                            help=f"Status do documento no checklist da Wanessa: {item['document_status']}",
                            key=f"{prefix}_{client_id}_{item['step_key']}_completed",
                            disabled=not can_edit_full_preparation,
                        )
                    payload.append(
                        {
                            "step_key": item["step_key"],
                            "step_label": item["step_label"],
                            "completed": launched,
                            "note": "",
                        }
                    )

        backup_state = checkpoint_map.get("bkp_drive")
        backup_saved = st.checkbox(
            "BKP da Declaração salvo no drive?",
            value=bool(backup_state["completed"]) if backup_state is not None else False,
            disabled=not can_edit_full_preparation,
        )

        ready_state = checkpoint_map.get("confirmacao_pronto_revisao")
        ready_for_review = st.checkbox(
            "Confirma que a declaração foi preenchida com todos os dados disponíveis e que está pronta para revisão/correção? Sim, eu confirmo",
            value=bool(ready_state["completed"]) if ready_state is not None else False,
            disabled=not can_edit_full_preparation,
        )

        observation_state = checkpoint_map.get("observacoes_gerais")
        general_observation = st.text_area(
            "Observações Gerais da Declaração",
            value=normalize_text(observation_state["note"]) if observation_state is not None else "",
            height=140,
            disabled=not can_edit_full_preparation,
        )

        submitted = st.form_submit_button(
            "Salvar andamento",
            use_container_width=True,
            disabled=not can_edit_preparation,
        )

    if not submitted:
        return

    if supabase_client is None:
        st.warning("Para salvar andamento, use o login do Supabase.")
        return

    try:
        final_assigned_preparer = acting_as if assume_responsibility else normalize_text(current_responsible) or "Não atribuído"
        final_status = selected_status
        if ready_for_review:
            final_status = "PRONTO PARA REVISÃO"

        payload.extend(
            [
                {
                    "step_key": "bkp_drive",
                    "step_label": "BKP da Declaração salvo no drive?",
                    "completed": backup_saved,
                    "note": "",
                },
                {
                    "step_key": "confirmacao_pronto_revisao",
                    "step_label": "Confirmação pronta para revisão",
                    "completed": ready_for_review,
                    "note": "",
                },
                {
                    "step_key": "observacoes_gerais",
                    "step_label": "Observações gerais da declaração",
                    "completed": bool(normalize_text(general_observation)),
                    "note": normalize_text(general_observation),
                },
            ]
        )

        save_preparation_updates(
            supabase_client,
            client_id,
            final_assigned_preparer,
            final_status,
            acting_as,
            payload if can_edit_full_preparation else [],
            allow_checkpoint_updates=can_edit_full_preparation,
        )
        st.toast("Salvo!")
        st.success("Andamento atualizado com sucesso.")
        st.rerun()
    except Exception as exc:
        st.error(f"Não foi possível salvar o andamento: {exc}")


def render_preparation_editor(
    ctx: dict[str, Any],
    supabase_client,
    people_df,
    documents_df,
    checkpoints_df,
    team_df,
    user_profile: dict[str, object],
) -> None:
    st = ctx["st"]
    normalize_text = ctx["normalize_text"]
    build_available_preparation_queue = ctx["build_available_preparation_queue"]

    st.header("Preenchimento")

    acting_as = normalize_text(user_profile.get("display_name", "")) or "Equipe"
    can_edit_preparation = user_profile.get("permission_level") in {"full", "status_only"}
    can_edit_full_preparation = can_edit_preparation

    available_df = build_available_preparation_queue(people_df)
    my_df = _build_my_df(people_df, acting_as, normalize_text)
    review_return_df = my_df[my_df["Status Preenchimento"].astype(str).str.contains("AJUSTE", case=False, na=False)].copy()

    general_df = people_df.copy()

    available_tab, my_tab, general_tab = st.tabs(
        ["Disponíveis para preenchimento", "Minhas declarações", "Consulta geral"]
    )

    with available_tab:
        metric_1, metric_2, metric_3, metric_4 = st.columns(4)
        with metric_1:
            st.metric("Disponíveis", len(available_df))
        with metric_2:
            st.metric("Docs completos", int((available_df["Documentação"] == "Recebido total").sum()))
        with metric_3:
            st.metric("Docs parciais", int((available_df["Documentação"] == "Recebido parcial").sum()))
        with metric_4:
            st.metric(
                "Sem responsável",
                int(available_df["Responsável pelo Preenchimento"].map(lambda value: _is_unassigned(value, normalize_text)).sum()),
            )

        _render_queue_table(st, available_df)
        if not available_df.empty:
            selected_name = st.selectbox(
                "Selecione um cliente disponível para preenchimento",
                options=available_df.sort_values("NOME")["NOME"].tolist(),
                key="prep_available_client_select",
            )
            selected_row = available_df[available_df["NOME"] == selected_name].iloc[0]

            _render_client_header(st, selected_row)
            _render_support_panels(st, selected_row)
            _render_preparation_form(
                ctx,
                supabase_client,
                selected_row,
                checkpoints_df,
                documents_df,
                acting_as,
                can_edit_preparation,
                can_edit_full_preparation,
                prefix="prep_available",
            )

    with my_tab:
        _render_my_table(st, my_df)

        st.markdown("**Declarações devolvidas para ajuste**")
        if review_return_df.empty:
            st.caption("Nenhuma declaração sua está aguardando ajuste no momento.")
        else:
            st.dataframe(
                review_return_df[
                    [
                        "NOME",
                        "Grupo",
                        "Status Preenchimento",
                        "Documentação",
                        "Progresso Geral",
                        "Observações Gerais da Declaração",
                    ]
                ].sort_values(["Grupo", "NOME"]),
                use_container_width=True,
                hide_index=True,
            )

        if my_df.empty:
            return

        selected_name = st.selectbox(
            "Selecione uma declaração sua para atualizar",
            options=my_df.sort_values("NOME")["NOME"].tolist(),
            key="prep_my_client_select",
        )
        selected_row = my_df[my_df["NOME"] == selected_name].iloc[0]

        _render_client_header(st, selected_row)
        _render_support_panels(st, selected_row)
        _render_preparation_form(
            ctx,
            supabase_client,
            selected_row,
            checkpoints_df,
            documents_df,
            acting_as,
            can_edit_preparation,
            can_edit_full_preparation,
            prefix="prep_my",
        )

    with general_tab:
        filtered_general_df = _render_general_table(st, general_df, normalize_text)
        if filtered_general_df.empty:
            st.info("Nenhum cliente encontrado com os filtros atuais.")
            return

        selected_name = st.selectbox(
            "Selecione um cliente para transferir responsável ou atualizar documentos",
            options=filtered_general_df.sort_values("NOME")["NOME"].tolist(),
            key="prep_general_client_select",
        )
        selected_row = filtered_general_df[filtered_general_df["NOME"] == selected_name].iloc[0]
        _render_client_header(st, selected_row)
        _render_support_panels(st, selected_row)
        _render_general_client_admin(
            ctx,
            supabase_client,
            selected_row,
            checkpoints_df,
            documents_df,
            team_df,
            acting_as,
            can_edit_preparation,
            can_edit_preparation,
        )
