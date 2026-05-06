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


def render_review_page(
    ctx: dict[str, Any],
    people_df,
    snapshot_df,
    supabase_client,
    checkpoints_df,
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
