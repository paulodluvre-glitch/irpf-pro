# Checklist de Deploy do MVP

## Antes de publicar

- Confirmar que `requirements.txt`, `app.py`, `comercial.py`, `preenchimento.py`, `revisao.py`, `database.py`, `README.md`, `logogestao.png`, `.streamlit/config.toml` e `.streamlit/secrets.example.toml` vão para o repositório.
- Confirmar que `data/`, planilhas reais, PDFs e `.streamlit/secrets.toml` não vão para o git.
- Criar os secrets do deploy com `SUPABASE_URL` e `SUPABASE_ANON_KEY`.
- No Streamlit Community Cloud, selecionar Python `3.12` em `Advanced settings`.
- Conferir usuários no Supabase Auth e emails iguais aos da tabela `team_members`.
- Conferir se RLS está ativo no Supabase.
- Fazer login com pelo menos um usuário de cada perfil: Comercial, Preenchimento, Revisão e Cadastros.

## Testes manuais mínimos

- Wanessa: consultar cliente, alterar checklist de documentos e exportar relatório comercial.
- Paulo ou Heverton: acessar Cadastros, exportar XLSX completo, subir planilha teste, selecionar campos de atualização e cancelar sem aplicar.
- Preenchimento: assumir uma declaração disponível, transferir responsável na consulta geral, marcar documento como `SOLICITAR DOCUMENTO` e confirmar envio para revisão.
- Revisão: revisar uma declaração `PRONTO PARA REVISÃO`, enviar para `AJUSTE - HEVERTON` e finalizar uma em `TRANSMITIDO` ou `AGUARDANDO REUNIÃO`.

## Pontos de atenção pós-MVP

- Fortalecer RLS para aplicar permissões diretamente no banco, não só na interface.
- Criar trilha de auditoria para saber quem alterou cliente/documento/status.
- Definir política de backup/export diário do Supabase.
- Monitorar lentidão se a base passar de alguns milhares de clientes/documentos.
