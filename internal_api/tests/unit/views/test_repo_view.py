from unittest.mock import patch
import json

from rest_framework.reverse import reverse

from covreports.utils.tuples import ReportTotals
from django.test import override_settings

from codecov.tests.base_test import InternalAPITest
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory, CommitFactory, PullFactory, BranchFactory
from core.models import Repository
from internal_api.repo.repository_accessors import RepoAccessors
from internal_api.tests.unit.views.test_compare_view import build_mocked_report_archive


class RepositoryViewSetTestSuite(InternalAPITest):
    def _list(self, kwargs, query_params={}):
        return self.client.get(
            reverse('repos-list', kwargs={"orgName": self.org.username}),
            data=query_params
        )

    def _retrieve(self, kwargs):
        return self.client.get(reverse('repos-detail', kwargs=kwargs))

    def _update(self, kwargs, data={}):
        return self.client.patch(
            reverse('repos-detail', kwargs=kwargs),
            data=data,
            content_type="application/json"
        )

    def _destroy(self, kwargs):
        return self.client.delete(reverse('repos-detail', kwargs=kwargs))

    def _regenerate_upload_token(self, kwargs):
        return self.client.patch(reverse('repos-regenerate-upload-token', kwargs=kwargs))

    def _erase(self, kwargs):
        return self.client.patch(reverse('repos-erase', kwargs=kwargs))

    def _encode(self, kwargs, data):
        return self.client.post(reverse('repos-encode', kwargs=kwargs), data=data)


@patch("internal_api.repo.repository_accessors.RepoAccessors.get_repo_permissions")
class TestRepositoryViewSetList(RepositoryViewSetTestSuite):
    def setUp(self):
        self.org = OwnerFactory(username='codecov', service='github')

        self.repo1 = RepositoryFactory(author=self.org, active=True, private=True, name='A')
        self.repo2 = RepositoryFactory(author=self.org, active=True, private=True, name='B')

        repos_with_permission = [
            self.repo1.repoid,
            self.repo2.repoid,
        ]

        self.user = OwnerFactory(
            username='codecov-user',
            service='github',
            organizations=[self.org.ownerid],
            permission=repos_with_permission
        )

        self.client.force_login(user=self.user)

    def test_order_by_updatestamp(self, _):
        response = self._list(
            kwargs={"orgName": self.org.username},
            query_params={'ordering': 'updatestamp'}
        )

        assert response.data["results"][0]["repoid"] == self.repo1.repoid
        assert response.data["results"][1]["repoid"] == self.repo2.repoid

        reverse_response = self._list(
            kwargs={"orgName": self.org.username},
            query_params={'ordering': '-updatestamp'}
        )

        assert reverse_response.data["results"][0]["repoid"] == self.repo2.repoid
        assert reverse_response.data["results"][1]["repoid"] == self.repo1.repoid

    def test_order_by_name(self, _):
        response = self._list(
            kwargs={"orgName": self.org.username},
            query_params={'ordering': 'name'}
        )

        assert response.data["results"][0]["repoid"] == self.repo1.repoid
        assert response.data["results"][1]["repoid"] == self.repo2.repoid

        reverse_response = self._list(
            kwargs={"orgName": self.org.username},
            query_params={'ordering': '-name'}
        )

        assert reverse_response.data["results"][0]["repoid"] == self.repo2.repoid
        assert reverse_response.data["results"][1]["repoid"] == self.repo1.repoid

    @patch("archive.services.ArchiveService.create_root_storage")
    @patch("archive.services.ArchiveService.read_chunks")
    def test_order_by_coverage(self, read_chunks_mock, *args):
        read_chunks_mock.return_value = []

        CommitFactory(repository=self.repo1, totals={"c": 25})
        CommitFactory(repository=self.repo1, totals={"c": 41})
        CommitFactory(repository=self.repo2, totals={"c": 32})

        response = self._list(
            kwargs={"orgName": self.org.username},
            query_params={'ordering': 'coverage'}
        )

        assert response.data["results"][0]["repoid"] == self.repo2.repoid
        assert response.data["results"][1]["repoid"] == self.repo1.repoid

        reverse_response = self._list(
            kwargs={"orgName": self.org.username},
            query_params={'ordering': '-coverage'}
        )

        assert reverse_response.data["results"][0]["repoid"] == self.repo1.repoid
        assert reverse_response.data["results"][1]["repoid"] == self.repo2.repoid

    def test_get_active_repos(self, _):
        RepositoryFactory(author=self.org, name='C')
        response = self._list(
            kwargs={"orgName": self.org.username},
            query_params={'active': True}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            len(response.data['results']),
            2,
            "got the wrong number of repos: {}".format(len(response.data['results']))
        )

    def test_get_inactive_repos(self, _):
        RepositoryFactory(author=self.org, name='C')
        response = self._list(
            kwargs={"orgName": self.org.username},
            query_params={'active': False}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            len(response.data['results']),
            1,
            "got the wrong number of repos: {}".format(len(response.data['results']))
        )

    def test_get_all_repos(self, mock_provider):
        RepositoryFactory(author=self.org, name='C')
        response = self._list(kwargs={"orgName": self.org.username})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            len(response.data['results']),
            3,
            "got the wrong number of repos: {}".format(len(response.data['results']))
        )


@patch("internal_api.repo.repository_accessors.RepoAccessors.get_repo_permissions")
class TestRepositoryViewSetDetailActions(RepositoryViewSetTestSuite):
    def setUp(self):
        self.org = OwnerFactory(username='codecov', service='github', service_id="5767537")
        self.repo = RepositoryFactory(author=self.org, active=True, private=True, name='repo1', service_id="201298242")

        self.user = OwnerFactory(
            username='codecov-user',
            service='github',
            organizations=[self.org.ownerid]
        )

        self.client.force_login(user=self.user)

    def test_retrieve_with_view_and_edit_permissions_succeeds(self, mocked_get_permissions):
        mocked_get_permissions.return_value = True, True
        response = self._retrieve(kwargs={"orgName": self.org.username, "repoName": self.repo.name})
        self.assertEqual(response.status_code, 200)
        assert 'upload_token' in response.data

    def test_retrieve_without_read_permissions_returns_403(self, mocked_get_permissions):
        mocked_get_permissions.return_value = False, False
        response = self._retrieve(kwargs={"orgName": self.org.username, "repoName": self.repo.name})
        assert response.status_code == 403

    def test_retrieve_without_edit_permissions_returns_detail_view_without_upload_token(self, mocked_get_permissions):
        mocked_get_permissions.return_value = True, False
        response = self._retrieve(kwargs={"orgName": self.org.username, "repoName": self.repo.name})
        assert response.status_code == 200
        assert "upload_token" not in response.data

    def test_destroy_repo_with_write_permissions_succeeds(self, mocked_get_permissions):
        mocked_get_permissions.return_value = True, True
        response = self._destroy(kwargs={"orgName": self.org.username, "repoName": self.repo.name})
        assert response.status_code == 204
        assert not Repository.objects.filter(name="repo1").exists()

    def test_destroy_repo_without_write_permissions_returns_403(self, mocked_get_permissions):
        mocked_get_permissions.return_value = True, False
        response = self._destroy(kwargs={"orgName": self.org.username, "repoName": self.repo.name})
        assert response.status_code == 403
        assert Repository.objects.filter(name="repo1").exists()

    def test_regenerate_upload_token_with_permissions_succeeds(self, mocked_get_permissions):
        mocked_get_permissions.return_value = True, True
        old_upload_token = self.repo.upload_token

        response = self._regenerate_upload_token(kwargs={"orgName": self.org.username, "repoName": self.repo.name})

        assert response.status_code == 200
        self.repo.refresh_from_db()
        assert str(self.repo.upload_token) == response.data["upload_token"]
        assert str(self.repo.upload_token) != old_upload_token

    def test_regenerate_upload_token_without_permissions_returns_403(self, mocked_get_permissions):
        mocked_get_permissions.return_value = False, False
        response = self._regenerate_upload_token(kwargs={"orgName": self.org.username, "repoName": self.repo.name})
        self.assertEqual(response.status_code, 403)

    def test_update_default_branch_with_permissions_succeeds(self, mocked_get_permissions):
        mocked_get_permissions.return_value = True, True
        new_default_branch = "dev"

        response = self._update(
            kwargs={"orgName": self.org.username, "repoName": self.repo.name},
            data={'branch': new_default_branch}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['branch'], 'dev', "got unexpected response: {}".format(response.data['branch']))
        self.repo.refresh_from_db()
        assert self.repo.branch == new_default_branch

    def test_update_default_branch_without_write_permissions_returns_403(self, mocked_get_permissions):
        mocked_get_permissions.return_value = True, False
        new_default_branch = "no_write_permissions"

        response = self._update(
            kwargs={"orgName": self.org.username, "repoName": self.repo.name},
            data={'branch': 'dev'}
        )
        self.assertEqual(response.status_code, 403)

    def test_erase_deletes_related_content_and_clears_cache_and_yaml(self, mocked_get_permissions):
        mocked_get_permissions.return_value = True, True

        CommitFactory(
            message='test_commits_base',
            commitid='9193232a8fe3429496956ba82b5fed2583d1b5eb',
            repository=self.repo,
        )

        PullFactory(
            pullid=2,
            repository=self.repo,
            author=self.repo.author,
        )

        BranchFactory(authors=[self.org.ownerid], repository=self.repo)

        self.repo.cache = {"cache": "val"}
        self.repo.yaml = {"yaml": "val"}
        self.repo.save()

        response = self._erase(kwargs={"orgName": self.org.username, "repoName": self.repo.name})
        assert response.status_code == 200

        assert not self.repo.commits.exists()
        assert not self.repo.pull_requests.exists()
        assert not self.repo.branches.exists()

        self.repo.refresh_from_db()
        assert self.repo.yaml == None
        assert self.repo.cache == None

    def test_erase_without_write_permissions_returns_403(self, mocked_get_permissions):
        mocked_get_permissions.return_value = True, False
        response = self._erase(kwargs={"orgName": self.org.username, "repoName": self.repo.name})
        assert response.status_code == 403

    def test_retrieve_returns_yaml(self, mocked_get_permissions):
        mocked_get_permissions.return_value = True, False

        yaml = {"yaml": "val"}
        self.repo.yaml = yaml
        self.repo.save()

        response = self._retrieve(kwargs={"orgName": self.org.username, "repoName": self.repo.name})
        assert response.status_code == 200
        assert response.data["yaml"] == yaml

    def test_activation_checks_if_credits_available_for_legacy_users(self, mocked_get_permissions):
        mocked_get_permissions.return_value = True, True

        self.org.plan = 'v4-5m'
        self.org.save()

        for i in range(4): # including the one used by other tests, should be 5 total
            RepositoryFactory(name=str(i) + "random", author=self.org, private=True, active=True)

        inactive_repo = RepositoryFactory(author=self.org, private=True, active=False)

        activation_data = {'active': True}
        response = self._update(
            kwargs={"orgName": self.org.username, "repoName": inactive_repo.name},
            data=activation_data
        )

        assert response.status_code == 403

    def test_encode_returns_200_on_success(self, mocked_get_permissions):
        mocked_get_permissions.return_value = True, True

        to_encode = {'value': "hjrok"}
        response = self._encode(
            kwargs={'orgName': self.org.username, 'repoName': self.repo.name},
            data=to_encode
        )

        assert response.status_code == 201

    @patch('internal_api.repo.views.encode_secret_string')
    def test_encode_returns_encoded_string_on_success(self, encoder_mock, mocked_get_permissions):
        mocked_get_permissions.return_value = True, True
        encrypted_string = "string:encrypted string"
        encoder_mock.return_value = encrypted_string

        to_encode = {'value': "hjrok"}
        response = self._encode(
            kwargs={'orgName': self.org.username, 'repoName': self.repo.name},
            data=to_encode
        )

        assert response.status_code == 201
        assert response.data["value"] == encrypted_string

    def test_encode_secret_string_encodes_with_right_key(self, _):
        from internal_api.repo.utils import encode_secret_string

        string_arg = "hi there"
        to_encode = '/'.join(( # this is the format expected by the key
            self.org.service,
            self.org.service_id,
            self.repo.service_id,
            string_arg
        ))

        from covreports.encryption import StandardEncryptor
        check_encryptor = StandardEncryptor()
        check_encryptor.key = b']\xbb\x13\xf9}\xb3\xb7\x03)*0Kv\xb2\xcet'

        encoded = encode_secret_string(to_encode)

        # we slice to take off the word "secret" prepended by the util
        assert check_encryptor.decode(encoded[7:]) == to_encode

    def test_retrieve_with_no_commits_doesnt_crash(self, mocked_get_permissions):
        mocked_get_permissions.return_value = True, True

        self.repo.commits.all().delete()

        response = self._retrieve(kwargs={"orgName": self.org.username, "repoName": self.repo.name})
        assert response.status_code == 200



class TestRepositoryViewSetVCR(object):

    @override_settings(DEBUG=True)
    def test_retrieve_with_latest_commit_files(self, mocker, db, client, codecov_vcr):
        mock_repo_accessor = mocker.patch.object(RepoAccessors, 'get_repo_permissions')
        mock_repo_accessor.return_value = True, True
        user = OwnerFactory(username='codecov', service='github')
        client.force_login(user=user)
        repo = RepositoryFactory(author=user, active=True, private=True, name='repo1')
        commit = CommitFactory.create(
            message='test_commits_base',
            commitid='9193232a8fe3429496956ba82b5fed2583d1b5eb',
            repository=repo,
        )
        expected_report_result = build_mocked_report_archive(mocker)

        response = client.get('/internal/codecov/repos/repo1/')
        content = json.loads(response.content.decode())
        print(content)
        assert content['can_edit']
        assert content['latest_commit']
        assert content['latest_commit']['commitid'] == commit.commitid
        assert content['latest_commit']['report']['totals'] == expected_report_result['totals']