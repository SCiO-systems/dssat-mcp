from fastapi import FastAPI, HTTPException, status, Body, Depends, Security
from fastapi.security import SecurityScopes, HTTPAuthorizationCredentials, HTTPBearer
import jwt
from typing import Optional
from dotenv import dotenv_values

###-------------------------------------------------------------------------------------------
class UnauthorizedException(HTTPException):
    def __init__(self, detail: str):
        """Returns HTTP 403"""
        super().__init__(status.HTTP_403_FORBIDDEN, detail=detail)


class UnauthenticatedException(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Requires authentication"
        )


class VerifyToken:
    # Does all the token verification using PyJWT
    def __init__(self):
        try:
            config = dotenv_values(".env")
            self.auth0_domain = config["AUTH0_DOMAIN"]
            self.auth0_algorithms = config["AUTH0_ALGORITHMS"]
            self.auth0_api_audience = config["AUTH0_API_AUDIENCE"]
            self.auth0_issuer = config["AUTH0_ISSUER"]
        except Exception as e:
            print("Error in getting env info for auth0.")
            raise e

        # This gets the JWKS from a given URL and does processing, so you can use any of the keys available
        jwks_url = f'{self.auth0_domain}.well-known/jwks.json'
        self.jwks_client = jwt.PyJWKClient(jwks_url)

    async def verify(self, security_scopes: SecurityScopes,
                     token: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer())):
        if token is None:
            raise UnauthenticatedException

        # This gets the 'kid' from the passed token
        try:
            signing_key = self.jwks_client.get_signing_key_from_jwt(token.credentials).key
        except jwt.exceptions.PyJWKClientError as error:
            print(1)
            raise UnauthorizedException(str(error))
        except jwt.exceptions.DecodeError as error:
            print(2)
            raise UnauthorizedException(str(error))

        try:
            payload = jwt.decode(token.credentials, signing_key,
                                 algorithms=self.auth0_algorithms,
                                 audience=self.auth0_api_audience,
                                 issuer=self.auth0_issuer,
                                 )
        except Exception as error:
            print(3)
            raise UnauthorizedException(str(error))

        return payload

