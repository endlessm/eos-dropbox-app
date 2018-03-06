bin_SCRIPTS = \
	eos-dropbox-app \
	xdg-open \
	$(NULL)

dist_pkgdata_SCRIPTS = \
	eos-dropbox-app.py \
	portallauncher.py \
	xdg-open.py \
	$(NULL)

do_edit = sed \
	-e "s|\@prefix\@|$(prefix)|" \
	-e "s|\@pkgdatadir\@|$(pkgdatadir)|"

%: %.in Makefile
	$(AM_V_GEN) $(do_edit) $<> $@

EXTRA_DIST = \
	eos-dropbox-app.in \
	xdg-open.in \
	$(NULL)

CLEANFILES = \
	eos-dropbox-app \
	xdg-open \
	$(NULL)
