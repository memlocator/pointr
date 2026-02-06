from concurrent import futures
import grpc
import recon_pb2
import recon_pb2_grpc
import httpx
import dns.resolver
import socket
from urllib.parse import urlparse
import re
from datetime import datetime


class ReconServicer(recon_pb2_grpc.ReconServiceServicer):
    def RunRecon(self, request, context):
        """Run reconnaissance on provided domains"""
        results = []

        for domain in request.domains:
            print(f"Running recon on: {domain}")
            result = self._recon_domain(domain)
            results.append(result)

        return recon_pb2.ReconResponse(results=results)

    def _recon_domain(self, domain):
        """Perform comprehensive recon on a single domain"""
        # Clean domain (remove http:// https:// www.)
        domain = self._clean_domain(domain)

        domain_recon = recon_pb2.DomainRecon(domain=domain)

        try:
            # 1. DNS Records
            domain_recon.dns_records.extend(self._get_dns_records(domain))

            # 2. SSL Certificates from crt.sh
            domain_recon.ssl_certificates.extend(self._get_ssl_certs(domain))

            # 3. Subdomains from crt.sh
            domain_recon.subdomains.extend(self._get_subdomains(domain))

            # 4. Security Headers
            headers = self._get_security_headers(domain)
            if headers:
                domain_recon.security_headers.CopyFrom(headers)

            # 5. WHOIS data
            whois_data = self._get_whois(domain)
            if whois_data:
                domain_recon.whois.CopyFrom(whois_data)

            # 6. ASN Information
            asn_info = self._get_asn_info(domain)
            if asn_info:
                domain_recon.asn_info.CopyFrom(asn_info)

        except Exception as e:
            domain_recon.error = str(e)
            print(f"Error during recon for {domain}: {e}")

        return domain_recon

    def _clean_domain(self, domain):
        """Extract clean domain from URL"""
        domain = domain.strip()
        domain = re.sub(r'^https?://', '', domain)
        domain = re.sub(r'^www\.', '', domain)
        domain = domain.split('/')[0]
        return domain

    def _get_dns_records(self, domain):
        """Get DNS records using dnspython"""
        records = []
        record_types = ['A', 'AAAA', 'MX', 'NS', 'TXT', 'SOA']

        for record_type in record_types:
            try:
                answers = dns.resolver.resolve(domain, record_type)
                for rdata in answers:
                    records.append(recon_pb2.DNSRecord(
                        type=record_type,
                        value=str(rdata),
                        ttl=int(answers.ttl)
                    ))
            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, Exception):
                pass

        return records

    def _get_ssl_certs(self, domain):
        """Get SSL certificates from crt.sh"""
        certs = []
        try:
            response = httpx.get(
                f'https://crt.sh/',
                params={'q': domain, 'output': 'json'},
                timeout=10.0,
                follow_redirects=True
            )

            if response.status_code == 200:
                data = response.json()
                # Limit to most recent 10 certificates
                seen_ids = set()
                for cert_data in data[:10]:
                    cert_id = cert_data.get('id')
                    if cert_id in seen_ids:
                        continue
                    seen_ids.add(cert_id)

                    san = cert_data.get('name_value', '').split('\n')

                    certs.append(recon_pb2.SSLCertificate(
                        issuer=cert_data.get('issuer_name', ''),
                        subject=cert_data.get('common_name', ''),
                        not_before=cert_data.get('not_before', ''),
                        not_after=cert_data.get('not_after', ''),
                        san_domains=san
                    ))
        except Exception as e:
            print(f"Error fetching SSL certs for {domain}: {e}")

        return certs

    def _get_subdomains(self, domain):
        """Extract unique subdomains from crt.sh certificates"""
        subdomains = set()
        try:
            response = httpx.get(
                f'https://crt.sh/',
                params={'q': f'%.{domain}', 'output': 'json'},
                timeout=10.0,
                follow_redirects=True
            )

            if response.status_code == 200:
                data = response.json()
                for cert_data in data[:100]:  # Limit processing
                    names = cert_data.get('name_value', '').split('\n')
                    for name in names:
                        name = name.strip().lower()
                        if name and name.endswith(domain) and '*' not in name:
                            subdomains.add(name)
        except Exception as e:
            print(f"Error fetching subdomains for {domain}: {e}")

        return sorted(list(subdomains))[:50]  # Return max 50 subdomains

    def _get_security_headers(self, domain):
        """Check security headers by making HTTP request"""
        try:
            response = httpx.get(
                f'https://{domain}',
                timeout=10.0,
                follow_redirects=True
            )

            headers = response.headers

            return recon_pb2.SecurityHeaders(
                strict_transport_security=headers.get('strict-transport-security', ''),
                content_security_policy=headers.get('content-security-policy', ''),
                x_frame_options=headers.get('x-frame-options', ''),
                x_content_type_options=headers.get('x-content-type-options', ''),
                referrer_policy=headers.get('referrer-policy', ''),
                permissions_policy=headers.get('permissions-policy', '')
            )
        except Exception as e:
            print(f"Error fetching security headers for {domain}: {e}")
            return None

    def _get_whois(self, domain):
        """Get WHOIS data using python-whois library or whois command"""
        try:
            import whois as whois_lib
            w = whois_lib.whois(domain)

            # Handle both single values and lists
            registrar = w.registrar if isinstance(w.registrar, str) else (w.registrar[0] if w.registrar else '')
            creation_date = self._format_date(w.creation_date)
            expiration_date = self._format_date(w.expiration_date)

            name_servers = w.name_servers if isinstance(w.name_servers, list) else ([w.name_servers] if w.name_servers else [])
            status = w.status if isinstance(w.status, list) else ([w.status] if w.status else [])

            return recon_pb2.WhoisData(
                registrar=registrar,
                creation_date=creation_date,
                expiration_date=expiration_date,
                name_servers=name_servers if name_servers else [],
                registrant_org=w.org if hasattr(w, 'org') and w.org else '',
                status=' | '.join(status) if status else ''
            )
        except Exception as e:
            print(f"Error fetching WHOIS for {domain}: {e}")
            return None

    def _format_date(self, date_value):
        """Format date from whois (handles lists and datetime objects)"""
        if not date_value:
            return ''
        if isinstance(date_value, list):
            date_value = date_value[0]
        if isinstance(date_value, datetime):
            return date_value.strftime('%Y-%m-%d')
        return str(date_value)

    def _get_asn_info(self, domain):
        """Get ASN information using Team Cymru DNS-based lookup"""
        try:
            # First resolve domain to IP
            ip = socket.gethostbyname(domain)

            # Reverse IP for Team Cymru query
            reversed_ip = '.'.join(reversed(ip.split('.')))

            # Query Team Cymru for ASN (origin.asn.cymru.com)
            try:
                answers = dns.resolver.resolve(f'{reversed_ip}.origin.asn.cymru.com', 'TXT')
                for rdata in answers:
                    txt = str(rdata).strip('"')
                    parts = txt.split(' | ')
                    if len(parts) >= 2:
                        asn = parts[0].strip()
                        country = parts[1].strip()

                        # Get ASN details
                        asn_details = self._get_asn_details(asn)

                        return recon_pb2.ASNInfo(
                            asn=f'AS{asn}',
                            organization=asn_details.get('org', ''),
                            ip_ranges=asn_details.get('ranges', []),
                            country=country
                        )
            except Exception as e:
                print(f"Error querying ASN for {domain}: {e}")

        except Exception as e:
            print(f"Error resolving IP for {domain}: {e}")

        return None

    def _get_asn_details(self, asn):
        """Get ASN organization name using Team Cymru"""
        try:
            answers = dns.resolver.resolve(f'AS{asn}.asn.cymru.com', 'TXT')
            for rdata in answers:
                txt = str(rdata).strip('"')
                parts = txt.split(' | ')
                if len(parts) >= 5:
                    return {
                        'org': parts[4].strip(),
                        'ranges': []  # Would need additional lookup for prefixes
                    }
        except Exception:
            pass

        return {'org': '', 'ranges': []}


def serve():
    """Start the gRPC server"""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    recon_pb2_grpc.add_ReconServiceServicer_to_server(
        ReconServicer(), server
    )
    server.add_insecure_port('[::]:50052')
    server.start()
    print("Recon service listening on port 50052")
    server.wait_for_termination()


if __name__ == '__main__':
    serve()
