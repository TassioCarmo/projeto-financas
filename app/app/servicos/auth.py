from flask import session


def usuario_logado() -> dict | None:
    usuario_id = session.get("usuario_id")
    if not usuario_id:
        return None
    return {
        "id": usuario_id,
        "nome": session.get("usuario_nome"),
        "email": session.get("usuario_email"),
    }


def iniciar_sessao(usuario: dict) -> None:
    session["usuario_id"] = str(usuario["id"])
    session["usuario_nome"] = usuario["nome"]
    session["usuario_email"] = usuario["email"]


def encerrar_sessao() -> None:
    session.clear()
