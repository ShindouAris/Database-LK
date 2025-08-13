from fastapi import APIRouter, HTTPException
from spotify import get_spotify_track_info
from pydantic import BaseModel
from logging import getLogger

class SpotifyRequestBase(BaseModel):
    spotifyUrl: str | None

class UtilsRouter(APIRouter): 
    def __init__(self, *args, **kwargs):
        super().__init__(prefix="/utils", *args, **kwargs)
        self.log = getLogger(__name__)
        self.add_api_route("/spotifyV2", self.get_spotify_tracks, methods=["POST"])
        
    async def get_spotify_tracks(self, requestData: SpotifyRequestBase):
        try: 
            tracks = await get_spotify_track_info(requestData.spotifyUrl)

            if not tracks: raise HTTPException(500, "Error trying to fetch spotify preview url")

            return tracks
        except HTTPException:
            raise
        except Exception as e:
            self.log.error(f"Error trying to fetch spotify url: {e}")
            raise HTTPException(500, "Error trying to get preview url for your spotify url")