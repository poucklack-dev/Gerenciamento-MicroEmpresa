from flask import session, redirect

def login_required(f):
    def wrapper(*args, **kwargs):
        if "usuario" not in session:
            return redirect("/login")
        return f(*args, **kwargs)

    wrapper.__name__ = f.__name__
    return wrapper
