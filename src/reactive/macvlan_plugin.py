import os

from charms.reactive import when, when_not, set_flag
from charms.reactive import endpoint_from_flag

from charmhelpers.core import unitdata
from charmhelpers.core.hookenv import network_get
from charmhelpers.core.templating import render

from charms.layer import status

kv = unitdata.kv()


@when_not('cni.interface.cidr.acquired')
def get_bind_interface_cidr():
    '''Acquire non-fan interface, cidr for the cni endpoint '''
    try:
        data = network_get('cni')
    except NotImplementedError:
        # Juju < 2.1
        status.blocked('Need Juju > 2.3')
        return

    if 'bind-addresses' not in data:
        # Juju < 2.3
        status.blocked('Need Juju > 2.3')
        return

    for bind_address in data['bind-addresses']:
        if bind_address['interfacename'].startswith('fan-'):
            continue
        if bind_address['interfacename'] and \
           bind_address['addresses'][0]['cidr']:
            kv.set('interfacename', bind_address['interfacename'])
            kv.set('cidr', bind_address['addresses'][0]['cidr'])
            set_flag('cni.interface.cidr.acquired')
            return

    status.blocked('Unable to create CNI configuration.')
    return


@when('cni.is-master',
      'cni.interface.cidr.acquired')
@when_not('macvlan.cni.configured')
def configure_master_cni():
    status.maint('Configuring MACVLAN CNI')
    cni = endpoint_from_flag('cni.is-master')
    cni.set_config(cidr=kv.get('cidr'))
    set_flag('macvlan.cni.configured')


@when('cni.is-worker',
      'cni.interface.cidr.acquired')
@when_not('macvlan.cni.configured')
def configure_worker_cni():
    ''' Configure MACVLAN CNI. '''
    status.maint('Configuring MACVLAN CNI')
    cni = endpoint_from_flag('cni.is-worker')
    os.makedirs('/etc/cni/net.d', exist_ok=True)
    ctxt = {'interfacename': kv.get('interfacename')}
    render('10-macvlan.conflist', '/etc/cni/net.d/10-macvlan.conflist', ctxt)
    cni.set_config(cidr=kv.get('cidr'))
    set_flag('macvlan.cni.configured')


@when('macvlan.cni.configured')
def set_cni_configured_status():
    status.active('macvlan cni configured')
