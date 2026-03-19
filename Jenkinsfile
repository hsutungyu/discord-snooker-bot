pipeline {
    agent any

    environment {
        REGISTRY     = "git.19371928.xyz"
        IMAGE_PATH   = "automation/discord-snooker"
        DEPLOY_FILE  = "deploy.yaml"
        // Credential IDs configured in Jenkins (see setup notes below)
        REGISTRY_CRED = "gitea-registry-creds"      // Username+Password credential
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

        stage('Build') {
            steps {
                sh "docker build -t ${env.FULL_IMAGE} ."
            }
        }

        stage('Push') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: env.REGISTRY_CRED,
                    usernameVariable: 'REG_USER',
                    passwordVariable: 'REG_PASS'
                )]) {
                    sh """
                        echo "\${REG_PASS}" | docker login "${env.REGISTRY}" \
                            -u "\${REG_USER}" --password-stdin
                        docker push "${env.FULL_IMAGE}"
                    """
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
                withCredentials([file(
                    credentialsId: env.KUBECONFIG_CRED,
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

    post {
        always {
            // Remove local image to keep the agent disk clean
            sh "docker rmi ${env.FULL_IMAGE} || true"
            sh "docker logout ${env.REGISTRY} || true"
        }
        success {
            echo "Deployed ${env.FULL_IMAGE} successfully."
        }
        failure {
            echo "Pipeline failed. Check logs above."
        }
    }
}
