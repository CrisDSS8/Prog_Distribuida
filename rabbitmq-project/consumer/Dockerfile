FROM maven:3.9-eclipse-temurin-21
WORKDIR /app

COPY Receive.java .

RUN echo '<project>\n\
  <modelVersion>4.0.0</modelVersion>\n\
  <groupId>com.example</groupId>\n\
  <artifactId>consumer</artifactId>\n\
  <version>1.0</version>\n\
  <dependencies>\n\
    <dependency>\n\
      <groupId>com.rabbitmq</groupId>\n\
      <artifactId>amqp-client</artifactId>\n\
      <version>5.20.0</version>\n\
    </dependency>\n\
    <dependency>\n\
      <groupId>org.slf4j</groupId>\n\
      <artifactId>slf4j-simple</artifactId>\n\
      <version>1.7.36</version>\n\
    </dependency>\n\
  </dependencies>\n\
  <build>\n\
    <plugins>\n\
      <plugin>\n\
        <groupId>org.apache.maven.plugins</groupId>\n\
        <artifactId>maven-jar-plugin</artifactId>\n\
        <configuration>\n\
          <archive>\n\
            <manifest>\n\
              <mainClass>Receive</mainClass>\n\
            </manifest>\n\
          </archive>\n\
          <outputDirectory>/app</outputDirectory>\n\
        </configuration>\n\
      </plugin>\n\
    </plugins>\n\
  </build>\n\
</project>' > pom.xml

RUN mkdir -p src/main/java && mv Receive.java src/main/java/
RUN mvn -q package dependency:copy-dependencies -DoutputDirectory=deps

CMD ["java", "-cp", "deps/*:consumer-1.0.jar", "Receive"]