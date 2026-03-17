# API Documentation Skill

## Purpose

Create and maintain accurate API endpoint documentation that reflects actual request/response contracts.

Use this skill when:
- Adding new API endpoints
- Modifying existing endpoint contracts
- Creating docs/api/endpoints.md documentation
- Adding OpenAPI/Swagger documentation
- Documenting error responses

## When NOT to Use

- User-facing feature documentation
- Code implementation details
- Internal implementation docs

## Discovery Steps

1. Find the route file in `app/api/routes/`
2. Check the endpoint function signature
3. Look for request/response models
4. Check for error handling
5. Find actual implementation in services

## Implementation Rules

1. **Document actual behavior**: What the endpoint actually does, not what it should do
2. **Include request/response schemas**: Show actual JSON structure
3. **Document errors**: List all possible error codes and messages
4. **Include examples**: Realistic request/response examples
5. **Match code**: Documentation must match actual implementation

## Verification

- Check endpoint actually responds as documented
- Verify request/response format
- Test error cases
- Ensure examples work
