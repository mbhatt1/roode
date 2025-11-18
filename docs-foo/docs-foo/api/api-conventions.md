# API Conventions

## Error Handling
All errors are returned with an error code and human-readable message. For example:

```json
{
  "error": {
    "code": 403, 
    "message": "You do not have permission to access this resource"
  }
}
```

## Pagination
List API methods support cursor-based pagination for efficiency. Include the `next_cursor` value in the request to get the next page of results.

## Authentication
API requests must include a valid access token in the `Authorization` header:

```
Authorization: Bearer <access_token>
```