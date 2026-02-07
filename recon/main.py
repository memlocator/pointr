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
import threading
import queue
from config import settings


class ReconServicer(recon_pb2_grpc.ReconServiceServicer):
    def Health(self, request, context):
        """Health check endpoint - returns service status without doing any actual recon"""
        return recon_pb2.HealthResponse(
            status="healthy",
            message="Recon service operational"
        )

    def RunRecon(self, request, context):
        """Run reconnaissance on provided domains"""
        results = []

        for domain in request.domains:
            print(f"Running recon on: {domain}")
            result = self._recon_domain(domain)
            results.append(result)

        return recon_pb2.ReconResponse(results=results)

    def RunReconStream(self, request, context):
        """Run reconnaissance with streaming updates (parallel execution)"""
        total_domains = len(request.domains)
        update_queue = queue.Queue()
        completed_count = [0]  # Use list for mutable counter
        lock = threading.Lock()

        def recon_worker(idx, domain):
            """Worker function to recon a single domain"""
            silent_mode = request.silent_mode
            mode_label = "SILENT" if silent_mode else "FULL"

            # Send start log
            update_queue.put(recon_pb2.ReconUpdate(
                type=recon_pb2.ReconUpdate.LOG,
                message=f"[{idx}/{total_domains}] Starting {mode_label} recon on {domain}"
            ))

            # Clean domain
            clean_domain = self._clean_domain(domain)
            domain_recon = recon_pb2.DomainRecon(domain=clean_domain)

            try:
                # DNS Records
                update_queue.put(recon_pb2.ReconUpdate(
                    type=recon_pb2.ReconUpdate.LOG,
                    message=f"[{clean_domain}] → Querying DNS records..."
                ))
                domain_recon.dns_records.extend(self._get_dns_records(clean_domain))
                update_queue.put(recon_pb2.ReconUpdate(
                    type=recon_pb2.ReconUpdate.LOG,
                    message=f"[{clean_domain}] ✓ Found {len(domain_recon.dns_records)} DNS records"
                ))

                # SSL Certificates
                update_queue.put(recon_pb2.ReconUpdate(
                    type=recon_pb2.ReconUpdate.LOG,
                    message=f"[{clean_domain}] → Fetching SSL certificates from crt.sh..."
                ))
                domain_recon.ssl_certificates.extend(self._get_ssl_certs(clean_domain))
                update_queue.put(recon_pb2.ReconUpdate(
                    type=recon_pb2.ReconUpdate.LOG,
                    message=f"[{clean_domain}] ✓ Found {len(domain_recon.ssl_certificates)} certificates"
                ))

                # Subdomains
                update_queue.put(recon_pb2.ReconUpdate(
                    type=recon_pb2.ReconUpdate.LOG,
                    message=f"[{clean_domain}] → Enumerating subdomains..."
                ))
                domain_recon.subdomains.extend(self._get_subdomains(clean_domain))
                update_queue.put(recon_pb2.ReconUpdate(
                    type=recon_pb2.ReconUpdate.LOG,
                    message=f"[{clean_domain}] ✓ Discovered {len(domain_recon.subdomains)} subdomains"
                ))

                # Security Headers (SKIP in silent mode - requires HTTP request to target)
                if not silent_mode:
                    update_queue.put(recon_pb2.ReconUpdate(
                        type=recon_pb2.ReconUpdate.LOG,
                        message=f"[{clean_domain}] → Checking security headers..."
                    ))
                    headers = self._get_security_headers(clean_domain)
                    if headers:
                        domain_recon.security_headers.CopyFrom(headers)
                        update_queue.put(recon_pb2.ReconUpdate(
                            type=recon_pb2.ReconUpdate.LOG,
                            message=f"[{clean_domain}] ✓ Analyzed security headers"
                        ))
                else:
                    update_queue.put(recon_pb2.ReconUpdate(
                        type=recon_pb2.ReconUpdate.LOG,
                        message=f"[{clean_domain}] ⊘ Skipped security headers (silent mode)"
                    ))

                # WHOIS
                update_queue.put(recon_pb2.ReconUpdate(
                    type=recon_pb2.ReconUpdate.LOG,
                    message=f"[{clean_domain}] → Performing WHOIS lookup..."
                ))
                whois_data = self._get_whois(clean_domain)
                if whois_data:
                    domain_recon.whois.CopyFrom(whois_data)
                    update_queue.put(recon_pb2.ReconUpdate(
                        type=recon_pb2.ReconUpdate.LOG,
                        message=f"[{clean_domain}] ✓ Retrieved WHOIS data"
                    ))

                # ASN (passive - only DNS queries)
                update_queue.put(recon_pb2.ReconUpdate(
                    type=recon_pb2.ReconUpdate.LOG,
                    message=f"[{clean_domain}] → Looking up ASN information..."
                ))
                asn_info = self._get_asn_info(clean_domain)
                if asn_info:
                    domain_recon.asn_info.CopyFrom(asn_info)
                    update_queue.put(recon_pb2.ReconUpdate(
                        type=recon_pb2.ReconUpdate.LOG,
                        message=f"[{clean_domain}] ✓ Found ASN: {asn_info.asn}"
                    ))

            except Exception as e:
                domain_recon.error = str(e)
                update_queue.put(recon_pb2.ReconUpdate(
                    type=recon_pb2.ReconUpdate.LOG,
                    message=f"[{clean_domain}] ✗ Error: {str(e)}"
                ))

            # Send result
            update_queue.put(recon_pb2.ReconUpdate(
                type=recon_pb2.ReconUpdate.RESULT,
                message=f"Completed {clean_domain}",
                result=domain_recon
            ))

            # Track completion
            with lock:
                completed_count[0] += 1
                if completed_count[0] == total_domains:
                    # All domains complete
                    update_queue.put(recon_pb2.ReconUpdate(
                        type=recon_pb2.ReconUpdate.COMPLETE,
                        message=f"Recon complete for {total_domains} domain(s)"
                    ))
                    update_queue.put(None)  # Sentinel to stop yielding

        # Start worker threads for each domain
        with futures.ThreadPoolExecutor(max_workers=min(settings.max_workers, total_domains)) as executor:
            for idx, domain in enumerate(request.domains, 1):
                executor.submit(recon_worker, idx, domain)

            # Yield updates as they come in from the queue
            while True:
                update = update_queue.get()
                if update is None:  # Sentinel value
                    break
                yield update

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
                settings.crt_sh_api_url,
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
                settings.crt_sh_api_url,
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
        """Get comprehensive ASN information using multiple sources"""
        try:
            # First resolve domain to IP
            ip = socket.gethostbyname(domain)

            # 1. Get basic ASN from Team Cymru (fast, reliable)
            asn_data = self._get_cymru_asn(ip)
            if not asn_data:
                return None

            asn = asn_data['asn']
            country = asn_data['country']
            bgp_prefix = asn_data['prefix']
            rir = asn_data['rir']

            # 2. Get detailed BGP data from RIPEstat (with BGPView fallback)
            bgp_data = self._get_ripestat_data(asn)

            # Fallback to BGPView if RIPEstat didn't return data
            if not bgp_data.get('org') and not bgp_data.get('prefixes_v4'):
                print(f"  Falling back to BGPView for AS{asn}")
                bgp_data = self._get_bgpview_data(asn)

            # 3. Get peering info from PeeringDB
            peering_data = self._get_peeringdb_data(asn)

            return recon_pb2.ASNInfo(
                asn=f'AS{asn}',
                organization=bgp_data.get('org', ''),
                ip_ranges=[],  # Deprecated - use prefixes_v4/v6
                country=country,
                prefixes_v4=bgp_data.get('prefixes_v4', [])[:10],  # Limit to first 10
                prefixes_v6=bgp_data.get('prefixes_v6', [])[:10],  # Limit to first 10
                prefix_count_v4=bgp_data.get('prefix_count_v4', 0),
                prefix_count_v6=bgp_data.get('prefix_count_v6', 0),
                peers=bgp_data.get('peers', [])[:20],  # Limit to first 20
                upstreams=bgp_data.get('upstreams', [])[:10],
                downstreams=bgp_data.get('downstreams', [])[:10],
                peering_policy=peering_data.get('policy', ''),
                network_type=peering_data.get('type', ''),
                peering_facilities=peering_data.get('facilities', [])[:10],
                rir=rir,
                abuse_contacts=bgp_data.get('abuse_contacts', []),
                bgp_prefix=bgp_prefix
            )

        except Exception as e:
            print(f"Error getting ASN info for {domain}: {e}")
            return None

    def _get_asn_details(self, asn):
        """Get ASN organization name using Team Cymru"""
        try:
            answers = dns.resolver.resolve(f'AS{asn}.{settings.cymru_asn_details_domain}', 'TXT')
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

    def _get_cymru_asn(self, ip):
        """Get enhanced ASN data from Team Cymru (includes prefix, RIR, country)"""
        try:
            # Reverse IP for Team Cymru query
            reversed_ip = '.'.join(reversed(ip.split('.')))

            # Query Team Cymru for full ASN data
            # Format: "ASN | BGP Prefix | Country | RIR | Allocated Date"
            answers = dns.resolver.resolve(f'{reversed_ip}.origin.asn.cymru.com', 'TXT')
            for rdata in answers:
                txt = str(rdata).strip('"')
                parts = [p.strip() for p in txt.split(' | ')]
                if len(parts) >= 4:
                    return {
                        'asn': parts[0],
                        'prefix': parts[1],
                        'country': parts[2],
                        'rir': parts[3],  # ARIN, RIPE, APNIC, etc.
                    }
        except Exception as e:
            print(f"Error querying Cymru for IP {ip}: {e}")

        return None

    def _get_ripestat_data(self, asn):
        """Get comprehensive BGP data from RIPEstat API"""
        try:
            # RIPEstat works for all RIRs, not just RIPE
            base_url = "https://stat.ripe.net/data"

            result = {
                'org': '',
                'prefixes_v4': [],
                'prefixes_v6': [],
                'prefix_count_v4': 0,
                'prefix_count_v6': 0,
                'peers': [],
                'upstreams': [],
                'downstreams': [],
                'abuse_contacts': []
            }

            # 1. Get announced prefixes (BGP routes)
            try:
                response = httpx.get(
                    f"{base_url}/announced-prefixes/data.json",
                    params={'resource': asn},
                    timeout=5.0
                )
                if response.status_code == 200:
                    data = response.json()
                    prefixes = data.get('data', {}).get('prefixes', [])

                    for prefix_obj in prefixes:
                        prefix = prefix_obj.get('prefix', '')
                        if ':' in prefix:  # IPv6
                            result['prefixes_v6'].append(prefix)
                        else:  # IPv4
                            result['prefixes_v4'].append(prefix)

                    result['prefix_count_v4'] = len(result['prefixes_v4'])
                    result['prefix_count_v6'] = len(result['prefixes_v6'])
            except Exception as e:
                print(f"Error getting RIPEstat prefixes for {asn}: {e}")

            # 2. Get AS neighbors (peers, upstreams, downstreams)
            try:
                response = httpx.get(
                    f"{base_url}/asn-neighbours/data.json",
                    params={'resource': asn},
                    timeout=5.0
                )
                if response.status_code == 200:
                    data = response.json()
                    neighbours = data.get('data', {}).get('neighbours', [])

                    for neighbour in neighbours:
                        asn_num = neighbour.get('asn')
                        neighbour_type = neighbour.get('type', '').lower()

                        if not asn_num:
                            continue

                        asn_str = f"AS{asn_num}"

                        if neighbour_type == 'left':  # Upstream (transit provider)
                            result['upstreams'].append(asn_str)
                        elif neighbour_type == 'right':  # Downstream (customer)
                            result['downstreams'].append(asn_str)
                        else:  # Peer
                            result['peers'].append(asn_str)
            except Exception as e:
                print(f"Error getting RIPEstat neighbours for {asn}: {e}")

            # 3. Get abuse contacts
            try:
                response = httpx.get(
                    f"{base_url}/abuse-contact-finder/data.json",
                    params={'resource': asn},
                    timeout=5.0
                )
                if response.status_code == 200:
                    data = response.json()
                    contacts = data.get('data', {}).get('abuse_contacts', [])
                    result['abuse_contacts'] = contacts
            except Exception as e:
                print(f"Error getting RIPEstat abuse contacts for {asn}: {e}")

            # 4. Get AS holder (organization name)
            try:
                response = httpx.get(
                    f"{base_url}/as-overview/data.json",
                    params={'resource': asn},
                    timeout=5.0
                )
                if response.status_code == 200:
                    data = response.json()
                    holder = data.get('data', {}).get('holder', '')
                    result['org'] = holder
            except Exception as e:
                print(f"Error getting RIPEstat AS overview for {asn}: {e}")

            return result

        except Exception as e:
            print(f"Error getting RIPEstat data for {asn}: {e}")
            return {
                'org': '',
                'prefixes_v4': [],
                'prefixes_v6': [],
                'prefix_count_v4': 0,
                'prefix_count_v6': 0,
                'peers': [],
                'upstreams': [],
                'downstreams': [],
                'abuse_contacts': []
            }

    def _get_bgpview_data(self, asn):
        """Get BGP data from BGPView API (fallback for RIPEstat)"""
        try:
            # Remove 'AS' prefix if present
            asn_num = asn.replace('AS', '')

            response = httpx.get(
                f"https://api.bgpview.io/asn/{asn_num}",
                timeout=10.0,
                headers={'User-Agent': 'Pointr-Recon/1.0'}
            )

            if response.status_code == 200:
                data = response.json()
                asn_data = data.get('data', {})

                result = {
                    'org': asn_data.get('name', ''),
                    'prefixes_v4': [],
                    'prefixes_v6': [],
                    'prefix_count_v4': asn_data.get('ipv4_prefix_count', 0),
                    'prefix_count_v6': asn_data.get('ipv6_prefix_count', 0),
                    'peers': [],
                    'upstreams': [],
                    'downstreams': [],
                    'abuse_contacts': [asn_data.get('abuse_contacts', [])[0]] if asn_data.get('abuse_contacts') else []
                }

                # Get prefixes (limited to first 10 of each)
                prefixes = asn_data.get('prefixes', [])
                for prefix_obj in prefixes[:10]:
                    prefix = prefix_obj.get('prefix', '')
                    ip_version = prefix_obj.get('ip_version', 4)

                    if ip_version == 6:
                        result['prefixes_v6'].append(prefix)
                    else:
                        result['prefixes_v4'].append(prefix)

                # Get upstream/downstream from peers
                upstreams = asn_data.get('upstreams', [])
                for upstream in upstreams[:10]:
                    result['upstreams'].append(f"AS{upstream.get('asn', '')}")

                downstreams = asn_data.get('downstreams', [])
                for downstream in downstreams[:10]:
                    result['downstreams'].append(f"AS{downstream.get('asn', '')}")

                peers = asn_data.get('peers', [])
                for peer in peers[:20]:
                    result['peers'].append(f"AS{peer.get('asn', '')}")

                return result

        except Exception as e:
            print(f"Error getting BGPView data for {asn}: {e}")

        return {
            'org': '',
            'prefixes_v4': [],
            'prefixes_v6': [],
            'prefix_count_v4': 0,
            'prefix_count_v6': 0,
            'peers': [],
            'upstreams': [],
            'downstreams': [],
            'abuse_contacts': []
        }

    def _get_peeringdb_data(self, asn):
        """Get peering information from PeeringDB API"""
        try:
            # Remove 'AS' prefix if present
            asn_num = asn.replace('AS', '')

            response = httpx.get(
                f"https://api.peeringdb.com/api/net",
                params={'asn': asn_num},
                timeout=5.0,
                headers={'User-Agent': 'Pointr-Recon/1.0'}
            )

            if response.status_code == 200:
                data = response.json()
                networks = data.get('data', [])

                if networks:
                    net = networks[0]  # Get first match

                    # Map policy codes to readable strings
                    policy_map = {
                        'Open': 'Open',
                        'Selective': 'Selective',
                        'Restrictive': 'Restrictive',
                        'No': 'No Peering'
                    }

                    return {
                        'policy': policy_map.get(net.get('policy_general', ''), ''),
                        'type': net.get('info_type', ''),  # Cable/DSL, NSP, Content, etc.
                        'facilities': []  # Would need additional API calls
                    }
        except Exception as e:
            print(f"Error getting PeeringDB data for {asn}: {e}")

        return {'policy': '', 'type': '', 'facilities': []}


def serve():
    """Start the gRPC server"""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    recon_pb2_grpc.add_ReconServiceServicer_to_server(
        ReconServicer(), server
    )
    server.add_insecure_port(f'[::]:{ settings.recon_port}')
    server.start()
    print(f"Recon service listening on port {settings.recon_port}")
    server.wait_for_termination()


if __name__ == '__main__':
    serve()
