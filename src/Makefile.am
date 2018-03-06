bin_SCRIPTS = eos-dropbox-app

dist_pkgdata_SCRIPTS = \
	eos-dropbox-app.py \
	portallauncher.py \
	$(NULL)

do_edit = sed \
	-e "s|\@prefix\@|$(prefix)|" \
	-e "s|\@pkgdatadir\@|$(pkgdatadir)|"

eos-dropbox-app: eos-dropbox-app.in Makefile
	$(AM_V_GEN) $(do_edit) $<> $@

EXTRA_DIST = \
	eos-dropbox-app.in \
	$(NULL)

CLEANFILES = \
	eos-dropbox-app \
	$(NULL)
