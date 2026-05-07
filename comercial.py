from __future__ import annotations

from typing import Any


def _get_client_documents_df(documents_df, client_id: int, pd):
    if "client_id" not in documents_df.columns:
        return pd.DataFrame()
    return documents_df[documents_df["client_id"] == client_id].copy()


def _normalize_date_to_iso(value, pd) -> str | None:
    if pd.isna(value):
        return None
    return pd.to_datetime(value).date().isoformat()


def _notify_saved(st, message: str) -> None:
    st.toast("Salvo!")
    st.success(message)


def _notify_deleted(st, message: str) -> None:
    st.toast("Excluído!")
    st.success(message)


def _commercial_documentation_label(row) -> str:
    total_documents = int(row.get("total_documentos", 0) or 0)
    received_documents = int(row.get("documentos_recebidos", 0) or 0)
    documentation_value = str(row.get("Documentação", "") or "").strip()
    if total_documents == 0:
        return "Sem documentação listada"
    if received_documents == 0:
        return "Sem documentação recebida"
    return documentation_value or "Sem documentação recebida"


def _build_collection_message(client_name: str, missing_documents: str) -> str:
    pendencias = missing_documents.strip() or "Nenhuma pendência de documentos listada no momento."
    first_name = (client_name.strip().split(" ") or [client_name])[0].title()
    return (
        f"Olá, {first_name}, tudo bem?!\n\n"
        "Segue abaixo a lista de documentos que faltam para finalizarmos a sua declaração:\n\n"
        f"{pendencias}\n\n"
        "Poderia nos enviar essas informações até amanhã por favor? Pedimos que não deixe para última hora "
        "e qualquer dúvida ou auxílio ficamos a disposição! 🤝"
    )


def _render_document_checklist(
    ctx: dict[str, Any],
    supabase_client,
    client_documents_df,
    client_id: int,
    can_manage_records: bool,
    save_document_bulk_updates,
    key_prefix: str,
    button_label: str,
) -> None:
    st = ctx["st"]
    pd = ctx["pd"]
    date = ctx["date"]
    normalize_text = ctx["normalize_text"]

    if client_documents_df.empty:
        st.caption("Esse cliente ainda não tem documentos cadastrados.")
        return

    checklist_df = client_documents_df[["document_id", "documento_descricao", "Status", "Última Atualização", "Observação Documento"]].copy()
    checklist_df["Recebido"] = checklist_df["Status"].map(lambda value: normalize_text(value).upper() == "RECEBIDO")
    checklist_df["Última Atualização"] = pd.to_datetime(checklist_df["Última Atualização"], errors="coerce").dt.date
    checklist_df = checklist_df.rename(columns={"documento_descricao": "Documento", "Observação Documento": "Observação"})
    edited_docs_df = st.data_editor(
        checklist_df[["document_id", "Documento", "Recebido", "Última Atualização", "Observação"]],
        use_container_width=True,
        hide_index=True,
        disabled=["document_id", "Documento", "Última Atualização"],
        column_config={
            "Recebido": st.column_config.CheckboxColumn("Recebido?"),
            "Última Atualização": st.column_config.DateColumn("Última atualização", format="DD/MM/YYYY"),
            "Observação": st.column_config.TextColumn("Observação do documento"),
        },
        key=f"{key_prefix}_checklist_editor_{client_id}",
    )

    if st.button(
        button_label,
        use_container_width=True,
        disabled=not can_manage_records,
        key=f"{key_prefix}_save_checklist_{client_id}",
    ):
        try:
            original_dates = {
                int(row["document_id"]): row["Última Atualização"]
                for _, row in checklist_df.iterrows()
            }
            original_statuses = {
                int(row["document_id"]): bool(row["Recebido"])
                for _, row in checklist_df.iterrows()
            }
            original_status_labels = {
                int(row["document_id"]): normalize_text(row["Status"]).upper() or "SEM STATUS"
                for _, row in checklist_df.iterrows()
            }
            updates = []
            for _, row in edited_docs_df.iterrows():
                document_id = int(row["document_id"])
                received_now = bool(row["Recebido"])
                last_update = original_dates.get(document_id)
                if received_now and (pd.isna(last_update) or not original_statuses.get(document_id, False)):
                    last_update = date.today()
                status = "RECEBIDO" if received_now else original_status_labels.get(document_id, "PENDENTE")
                if not received_now and original_status_labels.get(document_id) == "RECEBIDO":
                    status = "PENDENTE"
                updates.append(
                    {
                        "document_id": document_id,
                        "Status": status,
                        "last_update": _normalize_date_to_iso(last_update, pd),
                        "Observação Documento": row.get("Observação", ""),
                    }
                )
            save_document_bulk_updates(supabase_client, updates, client_id)
            _notify_saved(st, "Checklist de documentos atualizado com sucesso.")
            st.rerun()
        except Exception as exc:
            st.error(f"Não foi possível atualizar o checklist: {exc}")


def _render_document_maintenance(
    ctx: dict[str, Any],
    supabase_client,
    client_documents_df,
    client_id: int,
    can_manage_records: bool,
    save_document_record,
    update_document_record,
    delete_document_record,
    key_prefix: str,
    show_list: bool = True,
    show_checklist: bool = True,
    show_forms: bool = True,
) -> None:
    st = ctx["st"]
    pd = ctx["pd"]
    date = ctx["date"]
    normalize_text = ctx["normalize_text"]
    document_type_options = ctx.get(
        "DOCUMENT_TYPE_OPTIONS",
        ["Despesas Dedutíveis", "Informe de Rendimentos", "Informes Bancários", "Outros"],
    )
    document_status_options = ctx.get("DOCUMENT_STATUS_OPTIONS", ["PENDENTE", "RECEBIDO", "SOLICITAR DOCUMENTO", "SEM STATUS"])

    if show_list and client_documents_df.empty:
        st.caption("Esse cliente ainda não tem documentos cadastrados.")
    elif show_list:
        for _, doc_row in client_documents_df.sort_values(["Tipo Documento", "Instituição"]).iterrows():
            status_label = normalize_text(doc_row["Status"]) or "SEM STATUS"
            last_update = doc_row["Última Atualização"]
            last_update_label = "sem data" if pd.isna(last_update) else pd.to_datetime(last_update).strftime("%d/%m/%Y")
            st.markdown(
                f"- **{normalize_text(doc_row['documento_descricao'])}** | status: `{status_label}` | atualização: `{last_update_label}`"
            )
            if normalize_text(doc_row.get("Observação Documento", "")):
                st.caption(f"Obs: {normalize_text(doc_row.get('Observação Documento', ''))}")

    if show_checklist:
        st.markdown("**Checklist rápido de recebimento**")
        _render_document_checklist(
            ctx,
            supabase_client,
            client_documents_df,
            client_id,
            can_manage_records,
            save_document_bulk_updates=ctx["save_document_bulk_updates"],
            key_prefix=key_prefix,
            button_label="Salvar checklist deste cliente",
        )

    if not show_forms:
        return

    st.markdown("**Adicionar documento à lista**")
    with st.form(f"{key_prefix}_document_add_form_{client_id}"):
        doc_col_1, doc_col_2 = st.columns(2)
        with doc_col_1:
            new_document_type = st.selectbox("Tipo de documento", options=document_type_options)
            new_institution = st.text_input("Instituição")
            new_status = st.selectbox("Status do documento", options=document_status_options)
        with doc_col_2:
            new_last_update = st.date_input("Última atualização", value=date.today())
            new_control_key = st.text_input("Chave de controle")
            new_notes = st.text_area("Observação do documento", height=90)
        add_document = st.form_submit_button(
            "Adicionar documento",
            use_container_width=True,
            disabled=not can_manage_records,
        )

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
                notes=new_notes,
            )
            _notify_saved(st, "Documento adicionado com sucesso.")
            st.rerun()
        except Exception as exc:
            st.error(f"Não foi possível adicionar o documento: {exc}")

    if not client_documents_df.empty and "document_id" in client_documents_df.columns:
        with st.expander("Editar ou remover documento específico"):
            editable_docs = {
                f"{row['Tipo Documento']} - {row['Instituição']} ({row['Status']})": row
                for _, row in client_documents_df.iterrows()
            }
            selected_doc_label = st.selectbox("Documento", options=list(editable_docs.keys()), key=f"{key_prefix}_doc_select_{client_id}")
            selected_doc_row = editable_docs[selected_doc_label]

            with st.form(f"{key_prefix}_document_edit_form_{client_id}_{int(selected_doc_row['document_id'])}"):
                edit_col_1, edit_col_2 = st.columns(2)
                with edit_col_1:
                    edit_type_options = list(dict.fromkeys([selected_doc_row["Tipo Documento"], *document_type_options]))
                    edit_document_type = st.selectbox(
                        "Tipo de documento atual",
                        options=edit_type_options,
                        index=0,
                    )
                    edit_institution = st.text_input("Instituição atual", value=selected_doc_row["Instituição"])
                    edit_status_options = list(dict.fromkeys([selected_doc_row["Status"], *document_status_options]))
                    edit_status = st.selectbox(
                        "Status atual",
                        options=edit_status_options,
                        index=0,
                    )
                with edit_col_2:
                    existing_doc_date = selected_doc_row["Última Atualização"]
                    existing_doc_date = date.today() if pd.isna(existing_doc_date) else pd.to_datetime(existing_doc_date).date()
                    edit_last_update = st.date_input("Última atualização atual", value=existing_doc_date)
                    edit_control_key = st.text_input("Chave de controle atual", value=selected_doc_row["chave_controle"])
                    edit_notes = st.text_area(
                        "Observação do documento",
                        value=normalize_text(selected_doc_row.get("Observação Documento", "")),
                        height=90,
                    )
                update_document = st.form_submit_button(
                    "Salvar alteração do documento",
                    use_container_width=True,
                    disabled=not can_manage_records,
                )

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
                        notes=edit_notes,
                    )
                    _notify_saved(st, "Documento atualizado com sucesso.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Não foi possível atualizar o documento: {exc}")

            if st.button(
                "Remover documento selecionado",
                use_container_width=True,
                type="secondary",
                disabled=not can_manage_records,
                key=f"{key_prefix}_remove_doc_{int(selected_doc_row['document_id'])}",
            ):
                try:
                    delete_document_record(supabase_client, int(selected_doc_row["document_id"]), client_id)
                    _notify_deleted(st, "Documento removido com sucesso.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Não foi possível remover o documento: {exc}")


def render_registry_page(
    ctx: dict[str, Any],
    supabase_client,
    people_df,
    documents_df,
    team_df,
    user_profile: dict[str, object],
    show_header: bool = True,
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
    save_client_record = ctx["save_client_record"]
    save_document_record = ctx["save_document_record"]
    update_document_record = ctx["update_document_record"]
    delete_document_record = ctx["delete_document_record"]
    delete_client_record = ctx["delete_client_record"]
    save_document_bulk_updates = ctx["save_document_bulk_updates"]

    if show_header:
        st.header("Atendimento comercial")
    if supabase_client is None:
        st.info("Faça login para consultar e manter os cadastros.")
        return

    can_manage_records = bool(user_profile.get("can_manage_records", False))
    assigned_options = list(
        dict.fromkeys(
            ["Não atribuído"]
            + sorted(
                set(
                    team_df["name"].dropna().map(canonical_preparer).tolist()
                    + ["Wanessa", "Paulo", "Valdivone", "Michelle", "Erlane", "Duda", "Malu", "Heverton", "Renato"]
                )
            )
        )
    )

    if not can_manage_records:
        st.warning("Seu usuário pode consultar, mas não alterar cadastros ou documentos.")

    selectable_names = ["Novo cliente"] + sorted(people_df["NOME"].dropna().unique().tolist())
    pending_selected_name = st.session_state.pop("registry_client_select_pending", None)
    selected_index = 0
    if pending_selected_name and pending_selected_name in selectable_names:
        st.session_state.pop("registry_client_select", None)
        selected_index = selectable_names.index(pending_selected_name)
    selected_name = st.selectbox(
        "Cliente",
        options=selectable_names,
        index=selected_index,
        key="registry_client_select",
    )
    selected_row = None if selected_name == "Novo cliente" else people_df[people_df["NOME"] == selected_name].iloc[0]
    client_id = int(selected_row["client_id"]) if selected_row is not None else None

    if selected_row is not None:
        info_col_1, info_col_2, info_col_3 = st.columns(3)
        with info_col_1:
            st.caption("Grupo")
            st.write(normalize_text(selected_row["Grupo"]) or "Não informado")
        with info_col_2:
            st.caption("Documentação")
            st.write(normalize_text(selected_row["Documentação"]) or "Sem documentação")
        with info_col_3:
            st.caption("Recebidos / Total")
            st.write(normalize_text(selected_row["Recebidos / Total"]) or "0 / 0")

    st.markdown("**Documentos cadastrados**")
    if selected_row is None:
        st.info("Para cadastrar documentos, primeiro salve o cliente. Depois a lista de documentos fica disponível aqui mesmo.")
        client_documents_df = pd.DataFrame()
    else:
        st.text_area(
            "Observações Gerais da Declaração",
            value=normalize_text(selected_row.get("Observações Gerais da Declaração", "")) or "Sem observações registradas.",
            height=110,
            disabled=True,
            key=f"commercial_observation_{client_id}",
        )
        client_documents_df = _get_client_documents_df(documents_df, client_id, pd)
        _render_document_maintenance(
            ctx,
            supabase_client,
            client_documents_df,
            client_id,
            can_manage_records,
            save_document_record,
            update_document_record,
            delete_document_record,
            key_prefix="commercial_client_checklist",
            show_forms=False,
        )

    st.divider()
    st.markdown("**Cadastro do cliente**")
    with st.form("client_maintenance_form"):
        col_1, col_2 = st.columns(2)
        with col_1:
            full_name = st.text_input("Nome completo", value=selected_row["NOME"] if selected_row is not None else "")
            group_name = st.text_input("Grupo", value=selected_row["Grupo"] if selected_row is not None else "")
            complexity = st.text_input(
                "Nível de complexidade",
                value=selected_row["Nivel de Complexidade"] if selected_row is not None else "",
            )
            meeting_status = st.text_input("Reunião", value=selected_row["Reunião"] if selected_row is not None else "")
            assigned_preparer = st.selectbox(
                "Responsável pelo preenchimento",
                options=assigned_options,
                index=assigned_options.index(selected_row["Responsável pelo Preenchimento"])
                if selected_row is not None and selected_row["Responsável pelo Preenchimento"] in assigned_options
                else 0,
            )
        with col_2:
            tax_status = st.selectbox(
                "Status da declaração",
                options=status_options,
                index=status_options.index(selected_row["Status Preenchimento"])
                if selected_row is not None and selected_row["Status Preenchimento"] in status_options
                else 0,
            )
            post_filing_status = st.text_input(
                "Status pós-envio",
                value=selected_row["Status Pós-Envio"] if selected_row is not None else "",
            )
            cpf = st.text_input("CPF", value=selected_row.get("CPF", "") if selected_row is not None else "")
            phone = st.text_input("Telefone", value=selected_row.get("Telefone", "") if selected_row is not None else "")
            gov_password = st.text_input(
                "Senha Gov",
                value=selected_row.get("Senha Gov", "") if selected_row is not None else "",
            )
            has_digital_certificate = st.checkbox(
                "Tem certificado digital",
                value=bool(selected_row.get("Tem Certificado Digital", False)) if selected_row is not None else False,
            )
            power_of_attorney = st.text_input(
                "Cadastro de procuração",
                value=selected_row.get("Cadastro de Procuração", "") if selected_row is not None else "",
            )

        saved_client = st.form_submit_button(
            "Salvar cliente",
            use_container_width=True,
            disabled=not can_manage_records,
        )

    if saved_client:
        try:
            normalized_name = normalize_key(full_name)
            saved_id = save_client_record(
                supabase_client,
                {
                    "normalized_name": normalized_name,
                    "full_name": normalize_text(full_name),
                    "group_name": canonical_group_label(group_name),
                    "meeting_status": normalize_text(meeting_status),
                    "complexity_level": canonical_complexity(complexity),
                    "tax_status": canonical_status(tax_status),
                    "assigned_preparer": canonical_preparer(assigned_preparer),
                    "post_filing_status": normalize_text(post_filing_status),
                    "documentation_status": selected_row["Documentação"] if selected_row is not None else "Sem documentação",
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
            st.session_state["registry_client_select_pending"] = normalize_text(full_name)
            _notify_saved(st, f"Cliente salvo com sucesso. ID {saved_id}.")
            st.rerun()
        except Exception as exc:
            st.error(f"Não foi possível salvar o cliente: {exc}")

    if selected_row is not None:
        st.divider()
        _render_document_maintenance(
            ctx,
            supabase_client,
            client_documents_df,
            client_id,
            can_manage_records,
            save_document_record,
            update_document_record,
            delete_document_record,
            key_prefix="commercial_client_maintenance",
            show_list=False,
            show_checklist=False,
            show_forms=True,
        )

    if selected_row is not None:
        with st.expander("Excluir cliente"):
            confirm_delete = st.checkbox(
                "Confirmo que quero excluir este cliente e seus documentos vinculados",
                key=f"confirm_delete_client_{client_id}",
            )
            if st.button(
                "Excluir cliente selecionado",
                use_container_width=True,
                type="secondary",
                disabled=not confirm_delete or not can_manage_records,
                key=f"delete_client_{client_id}",
            ):
                try:
                    delete_client_record(supabase_client, client_id)
                    _notify_deleted(st, "Cliente excluído com sucesso.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Não foi possível excluir o cliente: {exc}")


def render_commercial_page(
    ctx: dict[str, Any],
    people_df,
    supabase_client,
    documents_df,
    team_df,
    user_profile: dict[str, object],
) -> None:
    st = ctx["st"]
    pd = ctx["pd"]
    normalize_text = ctx["normalize_text"]

    st.header("Comercial")
    operation_tab, report_tab = st.tabs(["Atendimento e documentos", "Relatório de documentação"])
    with operation_tab:
        render_registry_page(
            ctx,
            supabase_client,
            people_df,
            documents_df,
            team_df,
            user_profile,
            show_header=False,
        )

    with report_tab:
        report_source_df = people_df.copy()
        report_source_df["Documentação"] = report_source_df.apply(_commercial_documentation_label, axis=1)
        if "Status para Preenchimento" not in report_source_df.columns:
            report_source_df["Status para Preenchimento"] = ""

        metric_1, metric_2, metric_3, metric_4, metric_5 = st.columns(5)
        with metric_1:
            st.metric("Clientes", len(report_source_df))
        with metric_2:
            st.metric("Docs completos", int((report_source_df["Documentação"] == "Recebido total").sum()))
        with metric_3:
            st.metric("Docs parciais", int((report_source_df["Documentação"] == "Recebido parcial").sum()))
        with metric_4:
            st.metric(
                "Sem documentação recebida",
                int((report_source_df["Documentação"] == "Sem documentação recebida").sum()),
            )
        with metric_5:
            st.metric(
                "Sem documentação listada",
                int((report_source_df["Documentação"] == "Sem documentação listada").sum()),
            )

        report_df = report_source_df[
            [
                "NOME",
                "Grupo",
                "Documentação",
                "Status para Preenchimento",
                "Recebidos / Total",
                "% documentação recebida",
                "documentos_enviados_lista",
                "documentos_faltantes_lista",
                "Telefone",
                "Responsável pelo Preenchimento",
                "Status Preenchimento",
            ]
        ].copy()
        report_df["% Recebido"] = report_df["% documentação recebida"].map(lambda value: f"{value:.1f}%")
        report_df = report_df.rename(
            columns={
                "documentos_enviados_lista": "Documentos recebidos",
                "documentos_faltantes_lista": "Documentos faltantes",
            }
        )[
            [
                "NOME",
                "Grupo",
                "Documentação",
                "Status para Preenchimento",
                "Recebidos / Total",
                "% Recebido",
                "Documentos recebidos",
                "Documentos faltantes",
                "Telefone",
                "Responsável pelo Preenchimento",
                "Status Preenchimento",
            ]
        ]
        doc_filter = st.multiselect(
            "Filtrar por documentação",
            options=sorted(report_df["Documentação"].unique()),
            default=sorted(report_df["Documentação"].unique()),
            key="commercial_doc_filter",
        )
        filtered_df = report_df[report_df["Documentação"].isin(doc_filter)].copy()
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)

        export_df = filtered_df.copy()
        export_df["Documentos recebidos"] = export_df["Documentos recebidos"].map(
            lambda value: normalize_text(str(value).replace("\n", " | "))
        )
        export_df["Documentos faltantes"] = export_df["Documentos faltantes"].map(
            lambda value: normalize_text(str(value).replace("\n", " | "))
        )
        st.download_button(
            "Exportar relatório comercial",
            data=export_df.to_csv(index=False, sep=";").encode("utf-8-sig"),
            file_name="relatorio_comercial_documentacao.csv",
            mime="text/csv",
        )

        st.divider()
        st.markdown("**Mensagem de cobrança para o cliente**")
        message_client_options = report_df["NOME"].dropna().tolist()
        if not message_client_options:
            st.info("Nenhum cliente disponível para gerar mensagem.")
            return

        selected_message_client = st.selectbox(
            "Cliente para gerar mensagem",
            options=message_client_options,
            key="commercial_message_client",
        )
        selected_message_row = report_df[report_df["NOME"] == selected_message_client].iloc[0]
        raw_missing_documents = str(selected_message_row["Documentos faltantes"] or "")
        if raw_missing_documents.strip():
            formatted_missing_documents = "\n".join(
                f"- {item.strip()}"
                for item in raw_missing_documents.split("\n")
                if item.strip()
            )
        else:
            formatted_missing_documents = "Nenhuma pendência de documentos listada no momento."

        message_text = _build_collection_message(selected_message_client, formatted_missing_documents)
        st.text_area(
            "Mensagem pronta",
            value=message_text,
            height=210,
            key=f"commercial_collection_message_{selected_message_client}",
        )
