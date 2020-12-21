"""
Your awesome Distance Vector router for CS 168

Based on skeleton code by:
  MurphyMc, zhangwen0411, lab352
"""

import sim.api as api
from cs168.dv import RoutePacket, \
                     Table, TableEntry, \
                     DVRouterBase, Ports, \
                     FOREVER, INFINITY

class DVRouter(DVRouterBase):

    # A route should time out after this interval
    ROUTE_TTL = 15

    # Dead entries should time out after this interval
    GARBAGE_TTL = 10

    # -----------------------------------------------
    # At most one of these should ever be on at once
    SPLIT_HORIZON = False
    POISON_REVERSE = False
    # -----------------------------------------------
    
    # Determines if you send poison for expired routes
    POISON_EXPIRED = False

    # Determines if you send updates when a link comes up
    SEND_ON_LINK_UP = False

    # Determines if you send poison when a link goes down
    POISON_ON_LINK_DOWN = False

    def __init__(self):
        """
        Called when the instance is initialized.
        DO NOT remove any existing code from this method.
        However, feel free to add to it for memory purposes in the final stage!
        """
        assert not (self.SPLIT_HORIZON and self.POISON_REVERSE), \
                    "Split horizon and poison reverse can't both be on"
        
        self.start_timer()  # Starts signaling the timer at correct rate.

        # Contains all current ports and their latencies.
        # See the write-up for documentation.
        self.ports = Ports()
        
        # This is the table that contains all current routes
        self.table = Table()
        self.table.owner = self
        self.last_table = Table()
        self.last_table.owner = self

    def add_static_route(self, host, port):
        """
        Adds a static route to this router's table.

        Called automatically by the framework whenever a host is connected
        to this router.

        :param host: the host.
        :param port: the port that the host is attached to.
        :returns: nothing.
        """
        # `port` should have been added to `peer_tables` by `handle_link_up`
        # when the link came up.
        assert port in self.ports.get_all_ports(), "Link should be up, but is not."
        self.table[host] = TableEntry(dst=host, port=port, latency=self.ports.get_latency(port), expire_time=FOREVER)
        self.send_routes(force=False)

    def handle_data_packet(self, packet, in_port):
        """
        Called when a data packet arrives at this router.

        You may want to forward the packet, drop the packet, etc. here.

        :param packet: the packet that arrived.
        :param in_port: the port from which the packet arrived.
        :return: nothing.
        """
        if packet.dst not in self.table:
            return
        entry = self.table[packet.dst]
        if entry.latency >= INFINITY:
            return
        self.send(packet, entry.port)
    def send_single(self, force=False, port=None):
        """
        Send route advertisements for a single port in the table
        Do NOT update last_table.
        """
        assert port is not None
        for host, entry in self.table.items():
            if not force and host in self.last_table and self.last_table[host] == entry: continue
            if not self.SPLIT_HORIZON or port != entry.port:
                self.send_route(port=port, dst=host, latency=entry.latency if entry.port!=port or not self.POISON_REVERSE else INFINITY)
        
    def send_routes(self, force=False, single_port=None):
        """
        Send route advertisements for all routes in the table and update last_table

        :param force: if True, advertises ALL routes in the table;
                      otherwise, advertises only those routes that have
                      changed since the last advertisement.
               single_port: if not None, sends updates only to that port; to
                            be used in conjunction with handle_link_up.
        :return: nothing.
        """
        if single_port:
            assert single_port in self.ports.get_all_ports()
            self.send_single(force, single_port)
        else:
            for port in self.ports.get_all_ports():
                self.send_single(force, port)
        self.last_table = self.table
        self.table = Table(self.last_table)
        assert id(self.last_table) != id(self.table)

    def expire_routes(self):
        """
        Clears out expired routes from table.
        accordingly.
        """
        nt = Table()
        for k, v in self.table.items():
            if v.expire_time > api.current_time():
                nt[k] = v
            elif self.POISON_EXPIRED and v.latency < INFINITY:
                nt[k] = TableEntry(dst=v.dst, port=v.port, latency=INFINITY, expire_time=api.current_time()+self.ROUTE_TTL)
        self.table = nt

    def handle_route_advertisement(self, route_dst, route_latency, port):
        """
        Called when the router receives a route advertisement from a neighbor.

        :param route_dst: the destination of the advertised route.
        :param route_latency: latency from the neighbor to the destination.
        :param port: the port that the advertisement arrived on.
        :return: nothing.
        """
        if route_latency == INFINITY: # poisoned
            if route_dst in self.table and self.table[route_dst].port == port:
                entry = self.table[route_dst]
                self.table[route_dst] = TableEntry(dst=route_dst, port=port, latency=INFINITY,
                    expire_time=self.ROUTE_TTL+api.current_time() if entry.latency<INFINITY else entry.expire_time)
        else:
            tim = route_latency + self.ports.get_latency(port)
            if (route_dst not in self.table) or (tim < self.table[route_dst].latency) or (port == self.table[route_dst].port):
                self.table[route_dst] = TableEntry(dst=route_dst, port=port, latency=tim, expire_time=self.ROUTE_TTL+api.current_time())
        self.send_routes(force=False)

    def handle_link_up(self, port, latency):
        """
        Called by the framework when a link attached to this router goes up.

        :param port: the port that the link is attached to.
        :param latency: the link latency.
        :returns: nothing.
        """
        self.ports.add_port(port, latency)
        if self.SEND_ON_LINK_UP:
            self.send_routes(force=True, single_port=port)

    def handle_link_down(self, port):
        """
        Called by the framework when a link attached to this router does down.

        :param port: the port number used by the link.
        :returns: nothing.
        """
        self.ports.remove_port(port)
        if self.POISON_ON_LINK_DOWN:
            for k, v in self.table.items():
                if v.port == port:
                    self.table[k] = TableEntry(dst=v.dst, port=port, latency=INFINITY, expire_time=self.ROUTE_TTL+api.current_time())
            self.send_routes(force=False)

