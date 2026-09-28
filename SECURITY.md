# Security policy

Bundle can execute configured commands and call configured HTTP runtimes. Do
not register an untrusted runtime against a project that contains sensitive
files or credentials. The current MVP does not provide a sandbox for child
processes; deployment-specific isolation is the operator's responsibility.

Please do not disclose vulnerabilities publicly until the maintainers have had
an opportunity to investigate. Report security issues privately to the
repository maintainers with a description, reproduction steps, impact, and any
proposed mitigation. Do not include secrets in reports.
