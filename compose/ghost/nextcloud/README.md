# Nextcloud

Docs: [https://nextcloud.com](https://nextcloud.com)

## Usage

External access may require that you manually configure your Fully Qualified Domain Name (FQDN) as a trusted domain within the application.  There is an environment variable set up for this in the "nextcloud task" which will most likely make manual configuration unnecessary.  If you get the following [screenshot](https://docs.nextcloud.com/server/14/admin_manual/installation/installation_wizard.html#trusted-domains) warning when trying to access nextcloud externally you'll need to manually set it up.

This can be accomplished in two commands.

```bash
# On the server where the docker containers are running
$ docker exec -it --user www-data nextcloud /bin/bash
$ php occ config:system:set trusted_domains INDEX_FOR_NEW_ENTRY_SEE_DOCS_LINK_BELOW --value=YOUR_FQDN_HERE --update-only
```

The above commands are documented in the administration guide for Nextcloud:

* [set array values](https://docs.nextcloud.com/server/14/admin_manual/configuration_server/occ_command.html#setting-an-array-configuration-value)

* [docker container docs, references environment variables](https://github.com/nextcloud/docker)

## Gotchas

- **docx/office files won't open**: Nextcloud Office (richdocuments) uses the
  built-in CODE server via `custom_apps/richdocumentscode/proxy.php`. The
  Collabora callback hits Nextcloud through traefik, so it arrives from a
  `phantomlink` docker IP (`172.20.0.0/16`) — NOT a LAN IP. The
  `richdocuments.wopi_allowlist` app config must include that subnet or every
  open fails with `WOPI request denied` in `data/nextcloud.log`:

  ```bash
  docker exec -u www-data nextcloud php occ config:app:set \
    richdocuments wopi_allowlist --value='192.168.1.0/24,172.20.0.0/16'
  ```

- `richdocumentscode` shows as Disabled in `occ app:list` yet the bundled
  coolwsd AppImage keeps running and proxy.php still serves discovery —
  the Disabled label does not reflect whether the CODE backend is up.

- **Creating a public share link headlessly**: there is no `occ share:create`;
  the OCS API needs an app password. With host access, drop the file into
  `data/<user>/files/` (pipe through `docker exec -i -u www-data nextcloud
  tee ...` to keep ownership right), `occ files:scan --path="/<user>/files/<name>"`,
  then insert one row into `oc_share` (share_type=3, item_type='file',
  permissions=17, uid_owner/uid_initiator=<user>, file_source/item_source=
  fileid from `oc_filecache`, file_target='/<name>', token=15-char random).
  URL is `https://nextcloud.paynepride.com/s/<token>`; it shows up under
  Sharing → Share links in the UI like a normal share.
  **DB gotcha**: inside `nextcloud-mysql` the `MYSQL_HOST=mysql` env var
  makes the mysql client try host `mysql` — always pass `-h127.0.0.1`.
