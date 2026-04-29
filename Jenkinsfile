pipeline {
    // Runs on the pod template labelled 'python-ci', which provides:
    //   - kaniko   : gcr.io/kaniko-project/executor (build & push, no Docker daemon)
    //   - helm     : alpine/helm (kubectl + helm available for k8s operations)
    agent { label 'python-ci' }

    environment {
        REGISTRY      = "git.19371928.xyz"
        BE_IMAGE_PATH = "automation/discord-snooker-backend"
        FE_IMAGE_PATH = "automation/discord-snooker-frontend"
        VITE_API_URL  = "https://discord-snooker-backend.automation.k8s.19371928.xyz"
        // Credential ID configured in Jenkins
        REGISTRY_CRED = "gitea-jenkins-token"    // Username+Password credential
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
                    env.BE_FULL_IMAGE = "${env.REGISTRY}/${env.BE_IMAGE_PATH}:${env.TAG}"
                    env.FE_FULL_IMAGE = "${env.REGISTRY}/${env.FE_IMAGE_PATH}:${env.TAG}"
                    echo "Backend image: ${env.BE_FULL_IMAGE}"
                    echo "Frontend image: ${env.FE_FULL_IMAGE}"
                }
            }
        }

        stage('Build & Push Backend') {
            steps {
                container('kaniko') {
                    withCredentials([usernamePassword(
                        credentialsId: 'gitea-jenkins-token',
                        usernameVariable: 'REG_USER',
                        passwordVariable: 'REG_PASS'
                    )]) {
                        sh '''
                            AUTH=$(printf "%s:%s" "$REG_USER" "$REG_PASS" | base64 -w 0)
                            mkdir -p /kaniko/.docker
                            printf '{"auths":{"%s":{"auth":"%s"}}}' \
                                "$REGISTRY" "$AUTH" > /kaniko/.docker/config.json
                        '''
                        sh """
                            /kaniko/executor \
                                --context=dir://${env.WORKSPACE} \
                                --dockerfile=${env.WORKSPACE}/Dockerfile.backend \
                                --destination=${env.BE_FULL_IMAGE} \
                                --cache=true \
                                --cache-repo=${env.REGISTRY}/${env.BE_IMAGE_PATH}/cache
                        """
                    }
                }
            }
        }

        stage('Build & Push Frontend') {
            steps {
                container('kaniko') {
                    withCredentials([usernamePassword(
                        credentialsId: 'gitea-jenkins-token',
                        usernameVariable: 'REG_USER',
                        passwordVariable: 'REG_PASS'
                    )]) {
                        sh '''
                            AUTH=$(printf "%s:%s" "$REG_USER" "$REG_PASS" | base64 -w 0)
                            mkdir -p /kaniko/.docker
                            printf '{"auths":{"%s":{"auth":"%s"}}}' \
                                "$REGISTRY" "$AUTH" > /kaniko/.docker/config.json
                        '''
                        sh """
                            /kaniko/executor \
                                --context=dir://${env.WORKSPACE} \
                                --dockerfile=${env.WORKSPACE}/Dockerfile.frontend \
                                --build-arg VITE_API_URL=${env.VITE_API_URL} \
                                --destination=${env.FE_FULL_IMAGE} \
                                --cache=true \
                                --cache-repo=${env.REGISTRY}/${env.FE_IMAGE_PATH}/cache
                        """
                    }
                }
            }
        }

        stage('Update k8s Manifests') {
            steps {
                script {
                    sh """
                        sed -i "s|${env.REGISTRY}/${env.BE_IMAGE_PATH}:[^ ]*|${env.BE_FULL_IMAGE}|g" \
                            k8s/backend.yaml
                    """
                    echo "k8s/backend.yaml updated to ${env.BE_FULL_IMAGE}"
                    sh """
                        sed -i "s|${env.REGISTRY}/${env.FE_IMAGE_PATH}:[^ ]*|${env.FE_FULL_IMAGE}|g" \
                            k8s/frontend.yaml
                    """
                    echo "k8s/frontend.yaml updated to ${env.FE_FULL_IMAGE}"
                }
            }
        }

        stage('Deploy to Kubernetes') {
            steps {
                container('helm') {
                    sh "kubectl apply -f k8s/backend.yaml"
                    sh """
                        kubectl rollout status deployment/discord-snooker-backend \
                            -n automation --timeout=120s
                    """
                    sh "kubectl apply -f k8s/frontend.yaml"
                    sh """
                        kubectl rollout status deployment/discord-snooker-frontend \
                            -n automation --timeout=120s
                    """
                    sh "kubectl apply -f k8s/httproutes.yaml"
                }
            }
        }
    }

    post {
        success {
            echo "Deployed ${env.BE_FULL_IMAGE} and ${env.FE_FULL_IMAGE} successfully."
        }
        failure {
            echo "Pipeline failed. Check logs above."
        }
    }
}
