# Product access specification (draft, v2)

The archive API may remove an archived record only when the authenticated caller owns the record's tenant. A record without tenant ownership must remain unchanged. Acceptance requires checking an unauthorized caller and confirming all other tenants' records remain intact.
