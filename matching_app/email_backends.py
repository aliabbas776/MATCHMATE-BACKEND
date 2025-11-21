import ssl

from django.core.mail.backends.smtp import EmailBackend as DjangoEmailBackend


class GmailEmailBackend(DjangoEmailBackend):
    """
    SMTP backend compatible with Python 3.13's smtplib. We override `open`
    to avoid passing deprecated arguments such as `keyfile`/`certfile` and we
    build SSL contexts manually when TLS/SSL is enabled.
    """

    def _ssl_context(self):
        context = ssl.create_default_context()
        if self.ssl_certfile and self.ssl_keyfile:
            context.load_cert_chain(certfile=self.ssl_certfile, keyfile=self.ssl_keyfile)
        return context

    def open(self):
        if self.connection:
            return False

        connection_params = {}
        if self.timeout is not None:
            connection_params['timeout'] = self.timeout

        try:
            if self.use_ssl:
                self.connection = self.connection_class(
                    self.host,
                    self.port,
                    context=self._ssl_context(),
                    **connection_params,
                )
            else:
                self.connection = self.connection_class(self.host, self.port, **connection_params)

                if self.use_tls:
                    self.connection.starttls(context=self._ssl_context())

            if self.username and self.password:
                self.connection.login(self.username, self.password)
            return True
        except OSError:
            if self.connection:
                try:
                    self.connection.close()
                except Exception:
                    pass
                finally:
                    self.connection = None
            if not self.fail_silently:
                raise
            return False

