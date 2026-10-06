import jenkins.model.Jenkins
import hudson.security.HudsonPrivateSecurityRealm
import hudson.security.FullControlOnceLoggedInAuthorizationStrategy
import hudson.plugins.git.GitSCM
import hudson.plugins.git.BranchSpec
import hudson.plugins.git.UserRemoteConfig
import org.jenkinsci.plugins.workflow.job.WorkflowJob
import org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition

Jenkins jenkins = Jenkins.get()
String username = System.getenv('JENKINS_ADMIN_USER') ?: 'admin'
String password = System.getenv('JENKINS_ADMIN_PASSWORD')
if (!password) {
    throw new IllegalStateException('JENKINS_ADMIN_PASSWORD is required')
}
if (!(jenkins.securityRealm instanceof HudsonPrivateSecurityRealm)) {
    def realm = new HudsonPrivateSecurityRealm(false)
    realm.createAccount(username, password)
    jenkins.setSecurityRealm(realm)
}
def strategy = new FullControlOnceLoggedInAuthorizationStrategy()
strategy.setAllowAnonymousRead(false)
jenkins.setAuthorizationStrategy(strategy)
jenkins.setNumExecutors(1)

if (jenkins.getItem('openbmc-ci') == null) {
    def job = jenkins.createProject(WorkflowJob, 'openbmc-ci')
    def remote = new UserRemoteConfig(System.getenv('TPO_REPOSITORY'), null, null, null)
    def scm = new GitSCM([remote], [new BranchSpec('*/main')], false, [], null, null, [])
    def definition = new CpsScmFlowDefinition(scm, 'lab7/Jenkinsfile')
    definition.setLightweight(true)
    job.setDefinition(definition)
    job.setDescription('Лабораторная №7: QEMU, Redfish API, Selenium WebUI, Locust; код из GitHub.')
    job.save()
}
jenkins.save()
println('Lab7: secured Jenkins and GitHub Pipeline job openbmc-ci configured')
