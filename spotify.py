import re
import json
import base64
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
from datetime import datetime
from typing import Dict, List, Optional, Any

class SpotifyURIParser:
    """Class để xử lý Spotify URI tương tự spotify-uri package"""
    
    @staticmethod
    def parse(url: str) -> Dict[str, str]:
        """Parse Spotify URL và trả về thông tin"""
        # Regex patterns cho các loại Spotify URL
        patterns = {
            'track': r'spotify\.com/track/([a-zA-Z0-9]+)',
            'album': r'spotify\.com/album/([a-zA-Z0-9]+)', 
            'artist': r'spotify\.com/artist/([a-zA-Z0-9]+)',
            'playlist': r'spotify\.com/playlist/([a-zA-Z0-9]+)',
            'episode': r'spotify\.com/episode/([a-zA-Z0-9]+)'
        }
        
        for track_type, pattern in patterns.items():
            match = re.search(pattern, url)
            if match:
                return {
                    'type': track_type,
                    'id': match.group(1)
                }
        
        # Thử với Spotify URI format
        uri_match = re.match(r'spotify:([^:]+):([a-zA-Z0-9]+)', url)
        if uri_match:
            return {
                'type': uri_match.group(1),
                'id': uri_match.group(2)
            }
            
        raise ValueError(f"Couldn't parse '{url}' as valid Spotify URL")
    
    @staticmethod
    def format_embed_url(parsed_url: Dict[str, str]) -> str:
        """Tạo embed URL từ parsed URL"""
        return f"https://open.spotify.com/embed/{parsed_url['type']}/{parsed_url['id']}"
    
    @staticmethod
    def format_open_url(uri: str) -> str:
        """Tạo open URL từ Spotify URI"""
        if uri.startswith('spotify:'):
            parts = uri.split(':')
            return f"https://open.spotify.com/{parts[1]}/{parts[2]}"
        return uri

class Spotify:
    """Main class để xử lý Spotify data"""
    
    TYPE = {
        'ALBUM': 'album',
        'ARTIST': 'artist', 
        'EPISODE': 'episode',
        'PLAYLIST': 'playlist',
        'TRACK': 'track'
    }
    
    ERROR = {
        'REPORT': 'Please report the problem at https://github.com/microlinkhq/spotify-url-info/issues.',
        'NOT_DATA': "Couldn't find any data in embed page that we know how to parse.",
        'NOT_SCRIPTS': "Couldn't find scripts to get the data."
    }
    
    SUPPORTED_TYPES = list(TYPE.values())
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def throw_error(self, message: str, html: str = "") -> None:
        """Throw error with message"""
        error_msg = f"{message}\n{self.ERROR['REPORT']}"
        raise TypeError(error_msg)
    
    def parse_data(self, html: str) -> Dict[str, Any]:
        """Parse HTML để lấy data từ các script tags"""
        soup = BeautifulSoup(html, 'html.parser')
        scripts = soup.find_all('script')
        
        if not scripts:
            self.throw_error(self.ERROR['NOT_SCRIPTS'], html)
        
        # Tìm script với type="resource"
        for script in scripts:
            if script.get('type') == 'resource' and script.string:
                try:
                    data = json.loads(base64.b64decode(script.string).decode('utf-8'))
                    return self.normalize_data({'data': data})
                except:
                    continue
        
        # Tìm script với id="initial-state"
        for script in scripts:
            if script.get('id') == 'initial-state' and script.string:
                try:
                    decoded = base64.b64decode(script.string).decode('utf-8')
                    data = json.loads(decoded)['data']['entity']
                    return self.normalize_data({'data': data})
                except:
                    continue
        
        # Tìm script với id="__NEXT_DATA__"
        for script in scripts:
            if script.get('id') == '__NEXT_DATA__' and script.string:
                try:
                    data = json.loads(script.string)
                    entity_data = data.get('props', {}).get('pageProps', {}).get('state', {}).get('data', {}).get('entity')
                    if entity_data:
                        return self.normalize_data({'data': entity_data})
                except:
                    continue
        
        # Tìm trong nội dung script có chứa dữ liệu JSON
        for script in scripts:
            if script.string:
                # Tìm JSON data trong script content
                try:
                    # Tìm pattern __NEXT_DATA__
                    if '__NEXT_DATA__' in script.string:
                        start = script.string.find('{')
                        if start != -1:
                            data = json.loads(script.string[start:])
                            entity_data = data.get('props', {}).get('pageProps', {}).get('state', {}).get('data', {}).get('entity')
                            if entity_data:
                                return self.normalize_data({'data': entity_data})
                except:
                    continue
        
        self.throw_error(self.ERROR['NOT_DATA'], html)
    
    async def create_get_data(self, url: str) -> Dict[str, Any]:
        """Lấy data từ Spotify embed URL"""
        parsed_url = self.get_parsed_url(url)
        print(f"Parsed URL: {parsed_url}")
        
        embed_url = SpotifyURIParser.format_embed_url(parsed_url)
        print(f"Embed URL: {embed_url}")
        
        response = self.session.get(embed_url)
        response.raise_for_status()
        
        return self.parse_data(response.text)
    
    def get_parsed_url(self, url: str) -> Dict[str, str]:
        """Parse và validate Spotify URL"""
        try:
            parsed_url = SpotifyURIParser.parse(url)
            if not parsed_url.get('type'):
                raise TypeError()
            return parsed_url
        except:
            raise TypeError(f"Couldn't parse '{url}' as valid URL")
    
    def get_date(self, data: Dict[str, Any]) -> Optional[str]:
        """Lấy release date"""
        release_date = data.get('releaseDate', {})
        if isinstance(release_date, dict):
            return release_date.get('isoString')
        return data.get('release_date')
    
    def get_artist_track(self, track: Dict[str, Any]) -> str:
        """Lấy tên nghệ sĩ từ track"""
        if track.get('show'):
            return track['show'].get('publisher', '')
        
        artists = track.get('artists', [])
        if not artists:
            return ''
        
        artist_names = [artist.get('name', '') for artist in artists if artist.get('name')]
        
        if len(artist_names) == 1:
            return artist_names[0]
        elif len(artist_names) == 2:
            return f"{artist_names[0]} & {artist_names[1]}"
        else:
            return ', '.join(artist_names[:-1]) + f" & {artist_names[-1]}"
    
    def get_tracks(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Lấy danh sách tracks"""
        track_list = data.get('trackList')
        if track_list:
            return [self.to_track(track) for track in track_list]
        return [self.to_track(data)]
    
    def get_images(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Lấy danh sách images"""
        cover_art = data.get('coverArt', {})
        if cover_art.get('sources'):
            return cover_art['sources']
        
        if data.get('images'):
            return data['images']
            
        visual_identity = data.get('visualIdentity', {})
        if visual_identity.get('image'):
            return visual_identity['image']
            
        return []
    
    def get_link(self, data: Dict[str, Any]) -> str:
        """Lấy Spotify open URL"""
        uri = data.get('uri', '')
        return SpotifyURIParser.format_open_url(uri)
    
    async def get_spotify_links(self, url: str) -> List[str]:
        """Lấy các link scdn từ Spotify page"""
        try:
            response = self.session.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            scdn_links = set()
            
            # Tìm tất cả elements và check attributes
            for element in soup.find_all():
                for attr_value in element.attrs.values():
                    if isinstance(attr_value, str) and 'p.scdn.co' in attr_value:
                        scdn_links.add(attr_value)
                    elif isinstance(attr_value, list):
                        for value in attr_value:
                            if isinstance(value, str) and 'p.scdn.co' in value:
                                scdn_links.add(value)
            
            return list(scdn_links)
        except Exception as e:
            raise Exception(f"Failed to fetch preview URLs: {str(e)}")
    
    async def get_preview(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Lấy preview information"""
        tracks = self.get_tracks(data)
        track = tracks[0] if tracks else {}
        
        date = self.get_date(data)
        spotify_url = self.get_link(data)
        preview_urls = await self.get_spotify_links(spotify_url)
        
        images = self.get_images(data)
        image_url = None
        if images:
            # Tìm image có width lớn nhất
            max_image = max(images, key=lambda x: x.get('width', 0))
            image_url = max_image.get('url')
        
        return {
            'date': datetime.fromisoformat(date.replace('Z', '+00:00')).isoformat() if date else None,
            'title': data.get('name'),  # tên bài hát
            'type': data.get('type'),   # Loại ví dụ album track
            'track': track.get('name'), # Tên Track
            'description': data.get('description') or data.get('subtitle') or track.get('description'),
            'artist': track.get('artist'),  # Tên nghệ sĩ
            'image': image_url,
            'audio': track.get('previewUrl'),      # Link nghe thử trả về là link
            'spotify_url': spotify_url,            # Link bài hát
            'preview_url': preview_urls,           # Link nghe thử bản trả về là chuỗi
            'preview_url_V2': track.get('previewUrl'),  # Link nghe thử trả về là link
        }
    
    def to_track(self, track: Dict[str, Any]) -> Dict[str, Any]:
        """Convert track data to standard format"""
        audio_preview = track.get('audioPreview', {})
        preview_url = None
        
        if track.get('isPlayable') and audio_preview:
            preview_url = audio_preview.get('url')
        
        return {
            'artist': self.get_artist_track(track) or track.get('subtitle'),
            'duration': track.get('duration'),
            'name': track.get('title') or track.get('name'),
            'previewUrl': preview_url,
            'uri': track.get('uri'),
            'description': track.get('description')
        }
    
    def normalize_data(self, data_wrapper: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize và validate data"""
        data = data_wrapper.get('data')
        
        if not data or not data.get('type') or not data.get('name'):
            raise ValueError("Data doesn't seem to be of the right shape to parse")
        
        if data['type'] not in self.SUPPORTED_TYPES:
            supported_types_str = ', '.join(self.SUPPORTED_TYPES)
            raise ValueError(f"Not an {supported_types_str}. Only these types can be parsed")
        
        # Normalize type from URI
        uri = data.get('uri', '')
        if uri:
            uri_parts = uri.split(':')
            if len(uri_parts) >= 2:
                data['type'] = uri_parts[1]
        
        return data
    
    async def get_spotify_track_info(self, url: str) -> Optional[Dict[str, Any]]:
        """Main function để lấy thông tin track từ Spotify URL"""
        try:
            print(f"Processing URL: {url}")
            # Lấy embed data
            res = await self.create_get_data(url)
            # Lấy chi tiết bản nhạc
            response = await self.get_preview(res)
            return response
        except Exception as error:
            print(f'Lỗi khi lấy preview: {error}')
            return None

# Sử dụng
async def get_spotify_track_info(url: str) -> Optional[Dict[str, Any]]:
    """Function wrapper để sử dụng dễ dàng"""
    spotify = Spotify()
    return await spotify.get_spotify_track_info(url)

# Example usage:
if __name__ == "__main__":
    import asyncio
    
    async def main():
        url = "https://open.spotify.com/track/3OVMe3H6iAxbLF8iD2UYrw?si=43000bf7493544c4"  # Example URL
        result = await get_spotify_track_info(url)
        if result:
            print(json.dumps(result, indent=2, ensure_ascii=False))
    
    asyncio.run(main())