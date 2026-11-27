def role_for(claims):
    return claims.get("role", "viewer")
