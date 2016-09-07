from plumbum import cli
from baiji import s3

# We intentionally override main() with different arguments than plumbum.cli.Application pylint: disable=arguments-differ

class ListCommand(cli.Application):
    DESCRIPTION = "list files on s3"
    uri = cli.Flag(["-B", "--uri"], help='This option does nothing. It used to return URIs instead of paths, but this is now the default.')
    detail = cli.Flag(['-l', '--detail'], help='print details, like `ls -l`')
    shallow = cli.Flag("--shallow", help='process key names hierarchically and return only immediate "children" (like ls, instead of like find)')
    def main(self, key):
        if self.uri:
            print "-B and --uri are deprecated options"
        try:
            keys = s3.ls(key, return_full_urls=True, require_s3_scheme=True, shallow=self.shallow)
            if self.detail:
                from baiji.util.console import sizeof_format_human_readable
                for key in keys:
                    info = s3.info(key)
                    enc = " enc" if info['encrypted'] else "    "
                    print "%s\t%s%s\t%s" % (sizeof_format_human_readable(info['size']), info['last_modified'], enc, key.encode('utf-8'),)
            else:
                print u"\n".join(keys).encode('utf-8')
        except s3.InvalidSchemeException as e:
            print e
            return 1

class InfoCommand(cli.Application):
    DESCRIPTION = "info for file on s3"
    def main(self, key):
        for k, v in sorted(s3.info(key).items(), key=lambda x: x[0]):
            print "%s: %s" % (k, v)

class RemoveCommand(cli.Application):
    DESCRIPTION = "delete files on s3"
    recursive = cli.Flag(['-r', '--recursive'], help='remove everything below key')
    force = cli.Flag(['-f', '--force'], help="don't prompt for confirmation on recursive rm")
    def main(self, key):
        if self.recursive:
            s3.rm_r(key, force=self.force)
        else:
            s3.rm(key)

class CopyCommand(cli.Application):
    DESCRIPTION = "copy files from or to s3"
    force = cli.Flag(['-f', '--force'], help='overwrite existing files')
    skip = cli.Flag(['-s', '--skip'], help='skip existing files when copy')
    progress = cli.Flag(['-P', '--progress'], help='show progress bar')
    recursive = cli.Flag(['-r', '--recursive'], help='copy prefix and everything under')
    recursive_parallel = cli.Flag(['-R', '--recursive-parallel'], help='copy prefix and everything under, in parallel')
    preserve_acl = cli.Flag('--preserve-acl', help='preserve ACL instead of inheriting from new bucket when copying from s3 to s3')
    encrypt = cli.Flag('--no-encrypt', default=True, help='Do not server side encrypt at rest')
    gzip = cli.Flag(['-z', '--gzip'], help='Store compressed')
    policy = cli.SwitchAttr('--policy', str, help='override policy when copying to s3 (e.g. private, public-read, bucket-owner-read')
    encoding = cli.SwitchAttr('--encoding', str, help='Content-Encoding: gzip, etc')
    def main(self, src, dst):
        kwargs = {
            'force': self.force,
            'progress': self.progress,
            'policy': self.policy,
            'preserve_acl': self.preserve_acl,
            'encoding': self.encoding,
            'encrypt': self.encrypt,
            'gzip': self.gzip,
            'skip': self.skip,
        }
        if self.recursive or self.recursive_parallel:
            s3.cp_r(src, dst, parallel=self.recursive_parallel, **kwargs)
        else:
            s3.cp(src, dst, **kwargs)

class MoveCommand(cli.Application):
    DESCRIPTION = "move files from or to s3"
    force = cli.Flag(['-f', '--force'], help='overwrite existing files')
    progress = cli.Flag(['-P', '--progress'], help='show progress bar')
    gzip = cli.Flag(['-z', '--gzip'], help='Store compressed')
    encrypt = cli.Flag('--no-encrypt', default=True, help='Do not server side encrypt at rest')
    def main(self, src, dst):
        s3.mv(src, dst, force=self.force, progress=self.progress, encrypt=self.encrypt, gzip=self.gzip)

class TouchCommand(cli.Application):
    DESCRIPTION = "touch a file on s3"
    def main(self, key):
        s3.touch(key)

class SyncCommand(cli.Application):
    DESCRIPTION = "move a directory tree from or to s3, a la rsync"
    progress = cli.Flag(['-P', '--progress'], help='show progress')
    guess_content_type = cli.Flag(['-g', '--guess-content-type'], help='Guess content type of file')
    policy = cli.SwitchAttr('--policy', str, help='override policy when copying to s3 (e.g. private, public-read, bucket-owner-read')
    encoding = cli.SwitchAttr('--encoding', str, help='Content-Encoding: gzip, etc')
    do_not_delete = cli.SwitchAttr(['-D', '--do-not-delete'], str, list=True, help='Path prefixes not to delete from the target')
    encrypt = cli.Flag('--no-encrypt', default=True, help='Do not server side encrypt at rest')
    def main(self, src, dst):
        kwargs = {
            'do_not_delete': self.do_not_delete,
            'progress': self.progress,
            'policy': self.policy,
            'encoding': self.encoding,
            'encrypt': self.encrypt,
            'guess_content_type': self.guess_content_type,
        }
        s3.sync(src, dst, **kwargs)

class ExistsCommand(cli.Application):
    DESCRIPTION = "check if a file exists on s3"
    retries = cli.SwitchAttr('--retries', int, help='how many times to retry', default=3)
    def main(self, key):
        if not s3.exists(key, retries_allowed=self.retries):
            return -1

class URLCommand(cli.Application):
    DESCRIPTION = "generate a temporary url"
    expire = cli.SwitchAttr('--expire', int, help='number of seconds before url expires', default=86400)
    def main(self, key):
        print s3.get_url(key, self.expire)

class MD5Command(cli.Application):
    DESCRIPTION = "get an md5sum"
    def main(self, key):
        print s3.md5(key)

class EtagCommand(cli.Application):
    DESCRIPTION = "get an etag. For files under 5gb, this is a md5sum, otherwise it is merely unique."
    fix = cli.Flag('--fix', help='try to convert a multipart etag to a single part etag')
    def main(self, key):
        if self.fix:
            etag = s3.etag(key)
            if "-" in etag:
                s3.cp(key, key, force=True)
                print "etag updated from {} to {}".format(etag, s3.etag(key))
        else:
            print s3.etag(key)

class CatCommand(cli.Application):
    DESCRIPTION = "print contents of key to stdout"
    def main(self, key):
        print s3.get_string(key)

class BucketsCommand(cli.Application):
    DESCRIPTION = "tools for working with buckets"
    create = cli.SwitchAttr('--create', str, help='create a new bucket')
    info = cli.SwitchAttr('--info', str, help='get info on a bucket')
    def main(self):
        if self.create:
            s3.create_bucket(self.create)
        elif self.info:
            for k, v in sorted(s3.bucket_info(self.info).items(), key=lambda x: x[0]):
                print "%s: %s" % (k, v)
        else:
            print "\n".join(s3.list_buckets())

class IsCommand(cli.Application):
    DESCRIPTION = "check that two files are the same"
    def main(self, key, other_key):
        if s3.md5(key) == s3.md5(other_key):
            print "files match"
        else:
            print "files DO NOT match"
            return -1