pipeline {
    // Runs on the pod template labelled 'python-ci', which provides:
    //   - kaniko   : gcr.io/kaniko-project/executor (build & push, no Docker daemon)
    //   - helm     : alpine/helm (kubectl + helm available for k8s operations)
    agent { label 'python-ci' }

    environment {
        REGISTRY        = "git.19371928.xyz"
        IMAGE_PATH      = "automation/discord-snooker"
        DEPLOY_FILE     = "deploy.yaml"
        // Credential IDs configured in Jenkins (see setup notes below)
        REGISTRY_CRED   = "gitea-jenkins-token"    // Username+Password credential
        KUBECONFIG_CRED = "k8s-kubeconfig"          // Secret File credential
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Set Tag') {
            steps {
                script {
                    env.TAG = sh(
                        script: 'date -u +"%Y%m%d-%H%M%S"',
                        returnStdout: true
                    ).trim()
                    env.FULL_IMAGE = "${env.REGISTRY}/${env.IMAGE_PATH}:${env.TAG}"
                    echo "Image: ${env.FULL_IMAGE}"
                }
            }
        }

        stage('Build & Push') {
            steps {
                container('kaniko') {
                    withCredentials([usernamePassword(
                        credentialsId: 'gitea-jenkins-token',
                        usernameVariable: 'REG_USER',
                        passwordVariable: 'REG_PASS'
                    )]) {
                        // Write registry auth where kaniko expects it
                        sh '''
                            AUTH=$(printf "%s:%s" "$REG_USER" "$REG_PASS" | base64 -w 0)
                            mkdir -p /kaniko/.docker
                            printf '{"auths":{"%s":{"auth":"%s"}}}' \
                                "$REGISTRY" "$AUTH" > /kaniko/.docker/config.json
                        '''
                        sh """
                            /kaniko/executor \
                                --context=dir://${env.WORKSPACE} \
                                --dockerfile=${env.WORKSPACE}/Dockerfile \
                                --destination=${env.FULL_IMAGE} \
                                --cache=true \
                                --cache-repo=${env.REGISTRY}/${env.IMAGE_PATH}/cache
                        """
                    }
                }
            }
        }

        stage('Update deploy.yaml') {
            steps {
                sh """
                    sed -i "s|${env.REGISTRY}/${env.IMAGE_PATH}:[^ ]*|${env.FULL_IMAGE}|g" \
                        "${env.DEPLOY_FILE}"
                """
                echo "deploy.yaml updated to ${env.FULL_IMAGE}"
            }
        }

        stage('Deploy to Kubernetes') {
            steps {
                container('helm') {
                    withCredentials([file(
                        credentialsId: 'k8s-kubeconfig',
                        variable: 'KUBECONFIG'
                    )]) {
                        sh "kubectl apply -f ${env.DEPLOY_FILE}"
                        sh """
                            kubectl rollout status deployment/discord-snooker \
                                -n automation --timeout=120s
                        """
                    }
                }
            }
        }
    }

    post {
        success {
            echo "Deployed ${env.FULL_IMAGE} successfully."
        }
        failure {
            echo "Pipeline failed. Check logs above."
        }
    }
}
