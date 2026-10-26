"""Ignore only Windows' already-reset socket shutdown callback, not task failures."""
def install(loop):
    previous = loop.get_exception_handler()
    def handle(loop, context):
        error = context.get('exception')
        callback = getattr(context.get('handle'), '_callback', None)
        name = getattr(callback, '__qualname__', '')
        if isinstance(error, ConnectionResetError) and getattr(error,'winerror',None)==10054 and name.endswith('_ProactorBasePipeTransport._call_connection_lost'):
            return
        if previous: previous(loop, context)
        else: loop.default_exception_handler(context)
    loop.set_exception_handler(handle)
    return previous
