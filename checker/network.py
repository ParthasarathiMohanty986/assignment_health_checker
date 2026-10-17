"""Bounded, public-Internet-only GETs. DNS results are pinned to the socket.

No cookies, credentials, proxy environment, arbitrary ports, or private targets.
Every redirect is resolved and validated again.
"""
import http.client
import ipaddress
import socket
import ssl
import time
from urllib.parse import urlsplit,urljoin

class NotVerifiable(Exception): pass

def resolve_public(url):
    try:
        p=urlsplit(url)
        if p.scheme not in ('http','https') or not p.hostname or p.username or p.password or p.port not in (None,80,443):
            raise NotVerifiable('Only public HTTP(S) URLs on ports 80/443 without embedded credentials are supported.')
        if p.query:
            raise NotVerifiable('Query-string URLs need review. Use a public credential-free resource URL without query parameters in this MVP.')
        port=p.port or (443 if p.scheme=='https' else 80)
        addresses=socket.getaddrinfo(p.hostname,port,type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise NotVerifiable('Private, loopback, link-local, and reserved network addresses are blocked.')
        return p,port,addresses[0][4][0]
    except NotVerifiable: raise
    except (ValueError,OSError): raise NotVerifiable('The URL is invalid or its hostname could not be resolved.')

def fetch_public(url):
    started=time.monotonic(); deadline=started+12
    for _ in range(4):
        p,port,address=resolve_public(url)
        remaining=deadline-time.monotonic()
        if remaining<=0: raise NotVerifiable('Request exceeded the 12-second time limit.')
        connection=http.client.HTTPConnection(p.hostname,port,timeout=min(remaining,6))
        try:
            sock=socket.create_connection((address,port),timeout=min(remaining,6))
            connection.sock=sock
            if p.scheme=='https': connection.sock=ssl.create_default_context().wrap_socket(sock,server_hostname=p.hostname)
            connection.request('GET',p.path or '/',headers={'User-Agent':'AssignmentHealth/1.0','Accept-Encoding':'identity','Connection':'close'})
            response=connection.getresponse()
            if response.status in (301,302,303,307,308):
                target=response.getheader('Location')
                if not target: raise NotVerifiable('Redirect response did not specify a destination.')
                url=urljoin(url,target);continue
            parts=[];size=0
            while True:
                remaining=deadline-time.monotonic()
                if remaining<=0: raise NotVerifiable('Response exceeded the 12-second time limit.')
                if connection.sock: connection.sock.settimeout(min(remaining,6))
                chunk=response.read1(65536)
                if not chunk:break
                size+=len(chunk)
                if size>2*1024*1024: raise NotVerifiable('Response exceeds the 2 MB inspection limit.')
                parts.append(chunk)
            return {'status':response.status,'body':b''.join(parts),'content_type':response.getheader('Content-Type',''),'elapsed_ms':round((time.monotonic()-started)*1000)}
        except NotVerifiable:raise
        except (OSError,http.client.HTTPException,ValueError):
            raise NotVerifiable('The request could not finish: connection, TLS, or timeout failure. Retry and inspect the service.')
        finally:connection.close()
    raise NotVerifiable('Too many redirects; destination not verified.')
